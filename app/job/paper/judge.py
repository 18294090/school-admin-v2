from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
from pyzbar import pyzbar
import os

line=[]
n=0
def open_answer_card(url1):
    global n
    img=cv2.imread(url1)
    n=img.shape[1]//82
    return(img)

def open_student_card(url):  
    img=None 
    if os.path.isfile(url):
        # 如果是路径，则读取图像
        img = cv2.imread(url)
    elif isinstance(url, np.ndarray):
        # 如果是数组，则直接使用
        img = url
    if img is None:
        return None 
    n=img.shape[1]//82
    img=img[n*1:-n*1,n*1:-n*1]
    return(img)

#读取识别二维码
def qr_recognize(pic,pos):
    if pic is None or pic.size == 0:
        return None
    global n
    if len(pic.shape)!=2:
        pic = cv2.cvtColor(pic, cv2.COLOR_BGR2GRAY)    
    pic=pic[pos[0]:pos[1],pos[2]:pos[3]]    
    #图像处理，提高二维码识别准确率
    if pic.dtype != np.uint8:
        pic = pic.astype(np.uint8)    
    # 去除噪点
    pic = cv2.medianBlur(pic, 3)
    # 二值化处理
    _, thresh = cv2.threshold(pic, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    #膨胀
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    pic = cv2.dilate(thresh, kernel, iterations=1)
    #腐蚀
    pic = cv2.erode(pic, kernel, iterations=1)
    #反色
    pic= cv2.bitwise_not(pic)
    barcodes =""
    barcodes = pyzbar.decode(pic)    
    barcodeData=[]
    for barcode in barcodes:
        barcodeData.append(barcode.data.decode('utf-8'))  # 二进制类型转成字符串
    return(barcodeData)

def pict(gray):  # 图像处理，二值化
    if gray is None:
        return None
    if len(gray.shape)!=2:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY) 
    #如果gray是空图像，返回一个空图像
    if gray.shape[0]==0:
        return None
    gray = cv2.medianBlur(gray, 5)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    # 二值化处理
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 73, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh=cv2.erode(thresh,kernel,iterations=3)
    thresh=cv2.dilate(thresh,kernel,iterations=4)
    binary_erosion =cv2.erode(thresh, kernel,iterations=5)#腐蚀
    binary_dilation =cv2.dilate(binary_erosion, kernel,iterations=5) #膨胀   
    return(binary_dilation)
 
def paper_ajust(original_image, target_image):
    #将目标图像大小调整为原图像大小
    target_image = cv2.resize(target_image, (original_image.shape[1], original_image.shape[0]))
    original_corners = find_corners(original_image)
    target_corners = find_corners(target_image)
    if original_corners is None or target_corners is None:
        return(None)
    # 将target_image透视变换
    try:
        M = cv2.getPerspectiveTransform(target_corners, original_corners)
        adjusted_image = cv2.warpPerspective(target_image, M, (original_image.shape[1], original_image.shape[0]))
    except Exception as e:
        print(e)
        return(None)
    global n  
    return(adjusted_image)

def find_corners(img):
    global n
    # 转换为灰度图像    
    if len(img.shape)!=2:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) 
    else:
        gray=img 
    #模糊
    #gray=cv2.equalizeHist(gray)
    gray = cv2.medianBlur(gray, 5)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    # 二值化处理
    #_, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # 二值化处理
    #average_brightness = gray.mean()
    #提高亮度
    """while average_brightness < 240:
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=50)
        average_brightness=gray.mean()"""    
    thresh=cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 73, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh=cv2.erode(thresh,kernel,iterations=2)
    thresh=cv2.dilate(thresh,kernel,iterations=3) #膨胀,消除噪点
    erode = cv2.erode(thresh, kernel, iterations=4)#腐蚀，去除细节
    dilate = cv2.dilate(erode, kernel, iterations=4)#膨胀，增加细节    
    #canny=cv2.Canny(thresh, 50, 150)
    # 查找轮廓
    """cv2.namedWindow("gray", cv2.WINDOW_NORMAL)
    cv2.imshow("gray",dilate) 
    cv2.waitKey(0)
    cv2.destroyAllWindows()"""
    contours, _ = cv2.findContours(dilate, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    # 计算轮廓的质心，即中心点
    centers = []
    for cnt in contours:
        area = cv2.contourArea(cnt)        
        if area>=n**2*3 and area<=n**2*8:
            M = cv2.moments(cnt)
            if M['m00']!=0:            
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
            else:
                cx=cy=0            
            centers.append((cx, cy))
    # 确定四个顶点
    if len(centers)<4:
        print("无法定位四个顶点")
        return(None)
    top_left = min(centers, key=lambda x: x[0] + x[1])
    bottom_right = max(centers, key=lambda x: x[0] + x[1])
    top_right = max(centers, key=lambda x: x[0] - x[1])
    bottom_left = min(centers, key=lambda x: x[0] - x[1])    
    # 返回四个顶点的坐标   
    return(np.array([top_left,bottom_right,top_right,bottom_left],dtype=np.float32))

def number_pos(pic): #识别号码
    if pic is None:
        return("0")
    img=pict(pic[16*n:36*n,28*n:66*n])    
    cnts,h=cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pnt1=[]
    for cnt in cnts:
        area = cv2.contourArea(cnt)        
        if area>=n**2:            
            M = cv2.moments(cnt)
            cx = int(M['m10'] / M['m00'])
            cy = int(M['m01'] / M['m00'])
            pnt1.append((cx, cy))    
    result=""    
    pnt1.sort(key=lambda x:x[0])          
    for i in pnt1:
        result+=str((i[1]//n)//2)    
    return(result)

#矫正完成后，对画面进行切割，分别切割出考号填涂区，选择题区，和非选择题区
def paper_split(dst,s_n,line):
    num=dst[15*n:36*n,27*n:67*n]
    select=dst[43*n:43*n+(s_n+3)//4*2*n,6*n:77*n]
    c=[]
    for i in range(len(line)-1):
        c.append(dst[line[i]*n:line[i+1]*n,n*6:n*70])
    return(num,select,c)

def check_select(dst,m): #选择题阅卷，返回一个字典，{题目序号：选项} 
    pnt1=[]
    pnt={}
    #如果dst为空图像，返回一个空字典
    if dst.shape[0]==0:
        return(pnt)    
    s=pict(dst)
    cnts,h=cv2.findContours(s, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) 
    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area>n**2:
            M = cv2.moments(cnt)#计算轮廓的质心，即中心点
            cx = int(M['m10'] / M['m00'])
            cy = int(M['m01'] / M['m00'])
            pnt1.append((cx, cy))
    #将pnt1按照x坐标排序
    pnt1.sort(key=lambda x:x[0])
    ans=["A","B","C","D"]
    for i in pnt1:
        #根据坐标计算题目序号
        row=int((i[1]/n)//2)
        col=int(i[0]/n)
        order=(row)*4+col//15+1
        if order>m:
            print(order,m,"超出题目数量")
            continue
        s=(col%15-2)//3
        if s<0:
            continue
            
        elif s<=3:
            if order in pnt:
                if ans[s] in pnt[order]:
                    print("第%s选项已存在%s" %(order,ans[s]))
                    pass
                else:
                    pnt[order]+=ans[s]
            else:
                pnt[order]=ans[s]
        else:
            
            continue
            pnt[order]+=ans[3]
    return(pnt)

""" """
