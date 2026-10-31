"""Muse Wonder watches the clip and decides what to track, what sets the scale, and what matters.

  python see.py clip.mp4 -o plan.json      # then: python track.py clip.mp4 --plan plan.json
"""
import argparse, base64, json, os
import cv2

ASK = """You are the eyes of an autonomous physics lab. These are frames from one phone video, in time order.
Decide, with no human help:
1. which object(s) move in an interesting physical way (pendulum bob, ball, coin, water level...). Describe each as a short concrete noun phrase a segmentation model can find in every frame;
2. which object of KNOWN real size lies in the plane of motion to set the scale (paper sheet, credit card, coin, ruler, door frame...), and its longest visible side in metres;
3. what physical quantity is worth measuring and what law might govern it.
Reply with ONLY this JSON:
{"objects": [{"prompt": "...", "why": "..."}],
 "reference": {"prompt": "...", "size_m": 0.0, "why": "..."} or null,
 "quantity": "...",
 "note": "one-line description of the setup with every size you can estimate, for the analyst",
 "warnings": ["perspective, blur, occlusion or anything that will hurt the measurement"]}"""


def frames(path, n):
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or n
    out = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * (total - 1) // max(n - 1, 1))
        ok, f = cap.read()
        if ok:
            f = cv2.resize(f, None, fx=min(1, 768 / max(f.shape[:2])), fy=min(1, 768 / max(f.shape[:2])))
            out.append("data:image/jpeg;base64," + base64.b64encode(cv2.imencode(".jpg", f)[1]).decode())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default="plan.json")
    ap.add_argument("--frames", type=int, default=6, help="frames shown to the model (cost vs sight)")
    a = ap.parse_args()

    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("MODEL_BASE_URL", "https://api.meta.ai/v1"), api_key=os.environ["MODEL_API_KEY"])
    # ponytail: sends sampled frames as images, the common OpenAI-compatible format. Wonder also takes
    # video directly; switch to that once its input schema is checked on dev.meta.ai.
    content = [{"type": "text", "text": ASK}] + [{"type": "image_url", "image_url": {"url": u}} for u in frames(a.video, a.frames)]
    text = client.chat.completions.create(model=os.environ.get("WONDER_MODEL", "muse-wonder-1.0"),
                                          messages=[{"role": "user", "content": content}]).choices[0].message.content
    plan = json.loads(text[text.find("{"): text.rfind("}") + 1])
    if not plan.get("objects"):
        raise SystemExit(f"model saw nothing to track: {text[:300]}")
    json.dump(plan, open(a.out, "w"), indent=2)
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
