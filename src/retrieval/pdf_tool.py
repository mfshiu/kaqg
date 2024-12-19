from PIL import Image
import threading
import base64
import io
import json
import numpy as np
import fitz 
import pdfplumber 
import csv
import logging
import os
import sys  


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class PdfImport:
    def __init__(self, pdf_path):
        # 初始化 PDF 路徑與功能開關
        self.pdf_path = pdf_path
        self.enable_pdf_image = True
        self.enable_pdf_table = True  # 啟用表格處理功能

        # 初始化鎖，用於保護共享資料
        self.text_lock = threading.Lock()
        self.image_lock = threading.Lock()
        self.table_lock = threading.Lock()

        # 初始化提取資料
        self.extracted_text = ""
        self.extracted_images = []
        self.extracted_tables = []

    @staticmethod
    def _remove_non_latin_space(text: str):
        # 移除非拉丁字元之間的空格
        words = text.split(' ')
        for i, word in enumerate(words):
            if word:
                try:
                    word.encode('latin-1')
                    words[i] += ' '  # 拉丁字元，添加空格
                except UnicodeEncodeError:
                    pass  # 非拉丁字元，保留
        return ''.join(words)

    def extract_text(self):
        # 提取 PDF 文件的文字內容
        logger.info("開始提取文字內容")
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_index, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        text = text.replace("\n", "")
                        text = self._remove_non_latin_space(text)
                        logger.debug(f"PDF 第 {page_index+1} 頁文字:\n{text[:200]}...")
                        with self.text_lock:
                            self.extracted_text += text
            # 將提取的文字內容寫入檔案，存放至 _output 資料夾中
            text_file_path = os.path.join('_output', 'output_text.txt')
            with open(text_file_path, 'w', encoding='utf-8') as f:
                f.write(self.extracted_text)
            logger.info(f"文字內容提取完成，已保存到 {text_file_path}")
        except Exception as e:
            logger.error(f"提取文字時發生錯誤: {e}")

    def _image_percent_black(self, image):
        # 計算圖像中黑色像素的比例
        image_np = np.array(image.convert('RGB'))  # 確保圖像是 RGB 模式

        n_black = np.sum(
            (image_np[:, :, 0] < 50) &
            (image_np[:, :, 1] < 50) &
            (image_np[:, :, 2] < 50)
        )
        total_pixels = image_np[:, :, 0].size
        percent_black = (n_black / total_pixels) * 100
        return percent_black

    def extract_images(self):
        # 提取 PDF 文件中的圖像
        logger.info("開始提取圖像")
        try:
            pdf_file = fitz.open(self.pdf_path)
            for page_index in range(len(pdf_file)):
                page = pdf_file[page_index]
                image_list = page.get_images(full=True)
                if image_list:
                    logger.debug(f"在第 {page_index+1} 頁發現 {len(image_list)} 個圖像")
                    for image_index, img in enumerate(image_list, start=1):
                        xref = img[0]
                        base_image = pdf_file.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        image = Image.open(io.BytesIO(image_bytes))

                        # 跳過全黑的圖像
                        percent_black = self._image_percent_black(image)
                        if percent_black > 90:
                            logger.debug(f"第 {page_index+1} 頁的圖像 {image_index} 超過 90% 為黑色，跳過")
                            continue

                        # 將圖像轉換為PNG，存放至 _output 資料夾中
                        image_filename = f"image_page{page_index+1}_{image_index}.png"
                        image_file_path = os.path.join('_output', image_filename)
                        image.save(image_file_path, format='PNG')
                        logger.info(f"圖像已保存為 {image_file_path}")
                        with self.image_lock:
                            self.extracted_images.append(image_file_path)
                else:
                    logger.debug(f"第 {page_index+1} 頁沒有發現圖像")
            logger.info("圖像提取完成")
        except Exception as e:
            logger.error(f"提取圖像時發生錯誤: {e}")

    def extract_tables(self):
        # 提取 PDF 文件中的表格
        logger.info("開始提取表格")
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_index, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    if tables:
                        logger.debug(f"在第 {page_index+1} 頁發現 {len(tables)} 個表格")
                        for table_index, table in enumerate(tables, start=1):
                            table_filename = f"table_page{page_index+1}_{table_index}.csv"
                            table_file_path = os.path.join('_output', table_filename)
                            # 將表格保存為 CSV 文件到 _output 資料夾
                            with open(table_file_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.writer(f)
                                writer.writerows(table)
                            logger.info(f"表格已保存為 {table_file_path}")
                            with self.table_lock:
                                self.extracted_tables.append(table_file_path)
                    else:
                        logger.debug(f"第 {page_index+1} 頁沒有發現表格")
            logger.info("表格提取完成")
        except Exception as e:
            logger.error(f"提取表格時發生錯誤: {e}")

    def process(self):
        # 創建執行緒來處理文字提取
        text_thread = threading.Thread(target=self.extract_text)
        text_thread.start()

        # 創建執行緒來處理圖像提取
        if self.enable_pdf_image:
            image_thread = threading.Thread(target=self.extract_images)
            image_thread.start()
        else:
            image_thread = None

        # 創建執行緒來處理表格提取
        if self.enable_pdf_table:
            table_thread = threading.Thread(target=self.extract_tables)
            table_thread.start()
        else:
            table_thread = None

        # 等待所有執行緒完成
        text_thread.join()
        if image_thread:
            image_thread.join()
        if table_thread:
            table_thread.join()

        logger.info("PDF 處理完成")


# 主程式入口
if __name__ == "__main__":
    # 設定 PDF 檔案的路徑
    pdf_path = os.path.join('_output', 'test.pdf')  # _output 資料夾中的 test.pdf

    # 確保資料夾存在
    if not os.path.exists('_output'):
        os.makedirs('_output')

    # 確保 PDF 檔案存在
    if not os.path.exists(pdf_path):
        logger.error(f"找不到 PDF 檔案：{pdf_path}")
        sys.exit(1)

    # 開始處理 PDF
    pdf_importer = PdfImport(pdf_path)
    pdf_importer.process()
