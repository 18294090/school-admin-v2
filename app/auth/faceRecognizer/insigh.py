#insightface识别人脸，返回人脸特征
import cv2
import insightface
from insightface.app import FaceAnalysis

# 创建 FaceAnalysis 对象，它会自动加载 RetinaFace 和 ArcFace 模型
app = FaceAnalysis()

# 准备模型，使用 CPU
app.prepare(ctx_id=-1)

# 加载图像
img = cv2.imread('./faces/郑灏.jpg')

# 使用 FaceAnalysis 对象进行人脸检测和识别
faces = app.get(img)
#画框
for idx, face in enumerate(faces):
    bbox = face.bbox.astype(int)
    cv2.rectangle(img, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
    #画出关键点
    if face.landmark is not None:
        for i in range(5):
            cv2.circle(img, (int(face.landmark[i][0]), int(face.landmark[i][1])), 1, (0, 0, 255), 2)
    
# 显示图像
cv2.imshow('test', img)
cv2.waitKey(0)
cv2.destroyAllWindows()

# 打印识别结果
for idx, face in enumerate(faces):
    print(f"Face {idx + 1}:")
    print(f"  Gender: {'Male' if face.gender == 0 else 'Female'}")
    print(f"  Age: {face.age}")
    print(f"  Emotion: {face.emotion}")
    print(f"  Embedding shape: {face.embedding.shape}")
