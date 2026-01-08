#! python

import pyautogui
import time

while 1:
  pyautogui.moveRel(-10, 0)  # move mouse 10 pixels left
  time.sleep(2)
  pyautogui.moveRel(10, 0)  # move mouse 10 pixels right
  time.sleep(2)