from track import first_box as f

W, H = 1920, 1080
assert f({"box": [float("nan"), 0, 5, 5]}, None, W, H) is None
assert f({"box": [True, 0, 1, 1]}, None, W, H) is None
assert f({"box": [0, 0, 1, 1]}, None, W, H) == (0, 0, 1, 1)  # tiny pixel box, not normalised
assert f({"box": [0.1, 0.2, 0.3, 0.4]}, None, W, H) == (192, 216, 384, 216)  # normalised xyxy
assert f({"boxes": [[0.1, 0.2, 0.3, 0.4]]}, None, W, H) == (192, 216, 384, 216)  # list of boxes
assert f({"out": [{"box": [10, 20, 110, 220]}]}, None, W, H) == (10, 20, 100, 200)
assert f({"boxes": []}, None, W, H) is None and f({}, '{"box": [1, 2, 3, 4]}', W, H) == (1, 2, 2, 2)
print("ok")
