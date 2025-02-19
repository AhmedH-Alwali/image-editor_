import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QInputDialog, QMessageBox
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt

class ImageLabel(QLabel):
    """
    صنف فرعي من QLabel للتعامل مع أحداث الماوس (الرسم) مع تحويل الإحداثيات
    بحيث تتوافق مع أبعاد الصورة الأصلية حتى عند تغيير حجم النافذة.
    يدعم الرسم الحر، ورسم دائرة ومستطيل.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.parent = parent  # مرجع للنافذة الرئيسية
        self.drawing = False
        self.last_point = None      # يستخدم للرسم الحر
        self.start_point = None     # نقطة البداية عند رسم الدائرة أو المستطيل
        self.temp_image = None      # نسخة من الصورة قبل بدء رسم الشكل (للمعاينة)

    def mapToImageCoordinates(self, pos):
        """
        تحويل إحداثيات نقطة الفأرة (المستلمة بالنسبة للـ QLabel) إلى إحداثيات الصورة الأصلية.
        
        عند استخدام KeepAspectRatioByExpanding يتم ملء مساحة الـ QLabel بالصورة ويتم اقتصاص الأجزاء الزائدة.
        نحسب الإزاحة (offset) ثم نقوم بتحويل الإحداثيات.
        """
        label_width = self.width()
        label_height = self.height()

        pixmap = self.pixmap()
        if pixmap is None:
            return pos.x(), pos.y()

        # حجم الصورة المعروضة بعد استخدام KeepAspectRatioByExpanding
        scaled_width = pixmap.width()
        scaled_height = pixmap.height()

        # بما أن الصورة تمتد لتملأ الـ QLabel، فإن الجزء الظاهر هو المنطقة المركزية بحجم الـ QLabel.
        offset_x = (scaled_width - label_width) / 2
        offset_y = (scaled_height - label_height) / 2

        # نحسب إحداثيات النقطة داخل الصورة المعروضة (المقيَّمة)
        x_in_pixmap = pos.x() + offset_x
        y_in_pixmap = pos.y() + offset_y

        # تحويل الإحداثيات إلى إحداثيات الصورة الأصلية
        if self.parent.current_image is None:
            return int(x_in_pixmap), int(y_in_pixmap)
        orig_height, orig_width = self.parent.current_image.shape[:2]
        factor_x = orig_width / scaled_width
        factor_y = orig_height / scaled_height

        return int(x_in_pixmap * factor_x), int(y_in_pixmap * factor_y)

    def mousePressEvent(self, event):
        if self.parent.current_image is None:
            return

        if self.parent.shape_mode in ['circle', 'rectangle']:
            if event.button() == Qt.LeftButton:
                self.drawing = True
                self.start_point = self.mapToImageCoordinates(event.pos())
                self.temp_image = self.parent.current_image.copy()
        else:
            if event.button() == Qt.LeftButton:
                self.drawing = True
                self.last_point = self.mapToImageCoordinates(event.pos())

    def mouseMoveEvent(self, event):
        if self.parent.current_image is None or not self.drawing:
            return

        if self.parent.shape_mode == 'circle':
            current_point = self.mapToImageCoordinates(event.pos())
            dx = current_point[0] - self.start_point[0]
            dy = current_point[1] - self.start_point[1]
            radius = int(np.sqrt(dx * dx + dy * dy))
            preview = self.temp_image.copy()
            cv2.circle(preview, self.start_point, radius, (0, 0, 255), 2)
            self.parent.current_image_display = preview
            self.parent.update_image_display(preview=True)
        elif self.parent.shape_mode == 'rectangle':
            current_point = self.mapToImageCoordinates(event.pos())
            preview = self.temp_image.copy()
            cv2.rectangle(preview, self.start_point, current_point, (0, 255, 0), 2)
            self.parent.current_image_display = preview
            self.parent.update_image_display(preview=True)
        else:
            current_point = self.mapToImageCoordinates(event.pos())
            cv2.line(self.parent.current_image, self.last_point, current_point, (0, 0, 255), 2)
            self.last_point = current_point
            self.parent.update_image_display()

    def mouseReleaseEvent(self, event):
        if self.parent.current_image is None or not self.drawing:
            return

        if self.parent.shape_mode == 'circle':
            current_point = self.mapToImageCoordinates(event.pos())
            dx = current_point[0] - self.start_point[0]
            dy = current_point[1] - self.start_point[1]
            radius = int(np.sqrt(dx * dx + dy * dy))
            final_img = self.temp_image.copy()
            cv2.circle(final_img, self.start_point, radius, (0, 0, 255), 2)
            self.parent.current_image = final_img
            self.parent.update_image_display()
            # لا نقوم بإعادة تعيين الوضع حتى تتمكن من رسم المزيد من الدوائر
        elif self.parent.shape_mode == 'rectangle':
            current_point = self.mapToImageCoordinates(event.pos())
            final_img = self.temp_image.copy()
            cv2.rectangle(final_img, self.start_point, current_point, (0, 255, 0), 2)
            self.parent.current_image = final_img
            self.parent.update_image_display()
            # لا نقوم بإعادة تعيين الوضع حتى تتمكن من رسم المزيد من المستطيلات

        self.drawing = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_image = None           # الصورة الأصلية (مصفوفة NumPy)
        self.current_image_display = None   # صورة المعاينة أثناء الرسم
        self.shape_mode = None              # None (الرسم الحر) أو 'circle' أو 'rectangle'
        self.initUI()

    def initUI(self):
        self.setWindowTitle("تطبيق التعامل مع الصور والكاميرا باستخدام PyQt5")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.image_label = ImageLabel(self)
        self.image_label.setStyleSheet("background-color: gray;")
        self.image_label.setMinimumSize(400, 300)

        self.info_label = QLabel("لا توجد صورة")

        # أزرار الوظائف المختلفة (تم حذف أزرار التكبير والتصغير)
        self.btn_open = QPushButton("فتح صورة")
        self.btn_open.clicked.connect(self.open_image)

        self.btn_capture = QPushButton("التقاط صورة")
        self.btn_capture.clicked.connect(self.capture_image)

        self.btn_save = QPushButton("حفظ الصورة")
        self.btn_save.clicked.connect(self.save_image)

        self.btn_grayscale = QPushButton("تحويل للصورة الرمادية")
        self.btn_grayscale.clicked.connect(self.apply_grayscale)

        self.btn_mirror = QPushButton("صورة مرآة")
        self.btn_mirror.clicked.connect(self.apply_mirror)

        self.btn_text = QPushButton("إضافة نص")
        self.btn_text.clicked.connect(self.add_text)

        self.btn_circle = QPushButton("رسم دائرة")
        self.btn_circle.clicked.connect(self.start_circle_drawing)

        self.btn_rectangle = QPushButton("رسم مستطيل")
        self.btn_rectangle.clicked.connect(self.start_rectangle_drawing)

        # تنظيم التخطيطات
        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.addWidget(self.info_label)

        button_layout1 = QHBoxLayout()
        button_layout1.addWidget(self.btn_open)
        button_layout1.addWidget(self.btn_capture)
        button_layout1.addWidget(self.btn_save)
        button_layout1.addWidget(self.btn_grayscale)
        button_layout1.addWidget(self.btn_mirror)
        button_layout1.addWidget(self.btn_text)
        layout.addLayout(button_layout1)

        button_layout2 = QHBoxLayout()
        button_layout2.addWidget(self.btn_circle)
        button_layout2.addWidget(self.btn_rectangle)
        layout.addLayout(button_layout2)

        self.central_widget.setLayout(layout)
        self.resize(800, 600)

    def resizeEvent(self, event):
        """عند تغيير حجم النافذة يتم تحديث عرض الصورة لتتلاءم مع حجم الـ QLabel."""
        self.update_image_display()
        super().resizeEvent(event)

    def update_image_display(self, preview=False):
        """
        تحديث عرض الصورة في الـ QLabel.
        إذا كان preview=True نعرض الصورة المؤقتة (المعاينة أثناء الرسم) وإلا نعرض الصورة الأصلية.
        يتم تحجيم الصورة باستخدام KeepAspectRatioByExpanding لملء مساحة الـ QLabel.
        """
        if self.current_image is None:
            return

        img_to_show = self.current_image_display if preview and self.current_image_display is not None else self.current_image
        rgb_image = cv2.cvtColor(img_to_show, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        scaled_pixmap = QPixmap.fromImage(qimg).scaled(
            self.image_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
        self.update_image_info()

    def update_image_info(self):
        if self.current_image is not None:
            h, w = self.current_image.shape[:2]
            channels = self.current_image.shape[2] if len(self.current_image.shape) == 3 else 1
            self.info_label.setText(f"الأبعاد: {w}x{h}، عدد القنوات: {channels}")
        else:
            self.info_label.setText("لا توجد صورة")

    def open_image(self):
        fname, _ = QFileDialog.getOpenFileName(self, "فتح صورة", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if fname:
            img = cv2.imread(fname)
            if img is not None:
                self.current_image = img
                self.current_image_display = None
                self.update_image_display()
            else:
                QMessageBox.critical(self, "خطأ", "فشل قراءة الصورة!")

    def capture_image(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            QMessageBox.critical(self, "خطأ", "لا يمكن فتح الكاميرا")
            return

        # السماح للكاميرا ببعض الوقت للتسخين من خلال التقاط عدة إطارات
        ret = False
        for i in range(10):
            ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            self.current_image = frame
            self.current_image_display = None
            self.update_image_display()
        else:
            QMessageBox.critical(self, "خطأ", "فشل التقاط الصورة")

    def save_image(self):
        if self.current_image is None:
            QMessageBox.warning(self, "تنبيه", "لا توجد صورة لحفظها")
            return
        fname, _ = QFileDialog.getSaveFileName(self, "حفظ الصورة", "", "JPEG Files (*.jpg);;PNG Files (*.png)")
        if fname:
            cv2.imwrite(fname, self.current_image)
            QMessageBox.information(self, "تم الحفظ", "تم حفظ الصورة بنجاح")

    def add_text(self):
        if self.current_image is None:
            QMessageBox.warning(self, "تنبيه", "لا توجد صورة مرفوعة")
            return
        text, ok = QInputDialog.getText(self, "إدخال النص", "أدخل النص الذي تريد إضافته:")
        if ok and text:
            h, w = self.current_image.shape[:2]
            position = (w // 4, h // 2)
            cv2.putText(self.current_image, text, position, cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            self.update_image_display()

    def apply_grayscale(self):
        if self.current_image is None:
            QMessageBox.warning(self, "تنبيه", "لا توجد صورة مرفوعة")
            return
        gray = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2GRAY)
        self.current_image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        self.update_image_display()

    def apply_mirror(self):
        if self.current_image is None:
            QMessageBox.warning(self, "تنبيه", "لا توجد صورة مرفوعة")
            return
        self.current_image = cv2.flip(self.current_image, 1)
        self.update_image_display()

    def start_circle_drawing(self):
        if self.current_image is None:
            QMessageBox.warning(self, "تنبيه", "لا توجد صورة مرفوعة")
            return
        self.shape_mode = 'circle'
        # لم نعد نعرض رسالة تعليمات

    def start_rectangle_drawing(self):
        if self.current_image is None:
            QMessageBox.warning(self, "تنبيه", "لا توجد صورة مرفوعة")
            return
        self.shape_mode = 'rectangle'
        # لم نعد نعرض رسالة تعليمات

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
