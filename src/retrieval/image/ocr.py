import os
import logging
from paddleocr import PaddleOCR

# 設定日誌記錄
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class OcrProcessor:
    def __init__(self):
        # 初始化 PaddleOCR
        self.ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)  # 使用 PaddleOCR
        self.extracted_ocr_text = ""  # 用於儲存 OCR 辨識結果

    def process_images(self, image_folder):
        """
        處理指定資料夾中的所有圖片，進行 OCR 辨識並保存結果到 aaa.txt
        :param image_folder: 圖片所在的資料夾路徑
        """
        logger.info(f"開始處理資料夾中的圖片: {image_folder}")

        if not os.path.exists(image_folder):
            logger.error(f"資料夾不存在：{image_folder}")
            return

        # 獲取資料夾中的所有圖片檔案
        image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not image_files:
            logger.warning(f"資料夾 {image_folder} 中未發現圖片檔案，檢測到的檔案有：{os.listdir(image_folder)}")
            return

        # 處理每一張圖片
        for index, image_file in enumerate(image_files, start=1):
            image_path = os.path.join(image_folder, image_file)
            logger.info(f"處理圖片: {image_path}")
            try:
                # OCR 辨識圖片
                ocr_result = self.ocr.ocr(image_path, det=True, rec=True)
                text_result = "\n".join([line[1][0] for line in ocr_result[0]])  # 提取文字結果

                # 儲存辨識結果
                self.extracted_ocr_text += f"\n\n--- 圖片 {index} ({image_file}) 的 OCR 結果 ---\n{text_result}"
            except Exception as e:
                logger.error(f"處理圖片 {image_path} 時發生錯誤: {e}")

        # 輸出 OCR 辨識結果到 aaa.txt
        self._save_results()

    def _save_results(self):
        """
        保存 OCR 辨識結果到檔案
        """
        ocr_output_path = os.path.join(os.path.dirname(__file__), '../_output/aaa.txt')
        try:
            with open(ocr_output_path, 'w', encoding='utf-8') as ocr_file:
                ocr_file.write(self.extracted_ocr_text)
            logger.info(f"OCR 辨識結果已保存到: {ocr_output_path}")
        except Exception as e:
            logger.error(f"保存 OCR 結果時發生錯誤: {e}")


# 主程式入口
if __name__ == "__main__":
    # 假設圖片已經直接存放在 retrieval/_output 資料夾中
    image_folder = os.path.join(os.path.dirname(__file__), '../_output')  # 圖片資料夾

    # 初始化並處理圖片
    ocr_processor = OcrProcessor()
    ocr_processor.process_images(image_folder)
