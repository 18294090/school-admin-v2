
import cv2
import os
from PIL import Image, ImageDraw, ImageFont
import judge
import detect
import numpy as np
import time
cap=cv2.VideoCapture(0)
#每隔3秒获取一张图片
while True:
    ret,frame=cap.read()
    cv2.namedWindow('test',0)
    cv2.namedWindow('test1',0)
    if not ret:
        continue
    cv2.imshow('test1',frame)
    tag,frame1=detect.find_paper(frame)
    if tag!=2:
        
        corner=judge.find_corners(frame1)
        #画点
        for i in corner:
            
            cv2.circle(frame1, (int(i[0]), int(i[1])), 30, (0, 0, 255), 20)
            
        cv2.imshow('test',frame1)
        time.sleep(3)
        continue
    else:
        cv2.imshow("test",np.zeros((300,400,3)))
        cv2.waitKey(3)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
   
