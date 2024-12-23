import base64
import json
import os
import logging
import requests
import pdfplumber
import threading
from PIL import Image
import fitz
import io
import csv

# 初始化日誌
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

GPT_API_URL = "https://api.openai.com/v1/chat/completions"
GPT_API_KEY = ""

class PdfProcessor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.output_folder = "_output"
        self.page_contents = []  # 每頁的文字內容
        self.images = []  # 保存每頁的圖片內容
        self.tables = []  # 保存每頁的表格內容

        # 創建輸出資料夾
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

    def extract_text(self):
        logger.info("提取純文字內容...")
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_index, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        self.page_contents.append({"page_number": page_index + 1, "text": text, "image_descriptions": [], "table_descriptions": []})
                    else:
                        self.page_contents.append({"page_number": page_index + 1, "text": "", "image_descriptions": [], "table_descriptions": []})

            text_file = os.path.join(self.output_folder, "extracted_text.txt")
            with open(text_file, "w", encoding="utf-8") as f:
                for content in self.page_contents:
                    f.write(f"--- 第 {content['page_number']} 頁 ---\n")
                    f.write(content['text'] + "\n")
            logger.info(f"純文字內容已保存到: {text_file}")
        except Exception as e:
            logger.error(f"提取純文字時發生錯誤: {e}")

    def extract_images(self):
        logger.info("提取圖片內容...")
        try:
            pdf_file = fitz.open(self.pdf_path)
            for page_index in range(len(pdf_file)):
                page = pdf_file[page_index]
                images = page.get_images(full=True)
                for img_index, img in enumerate(images):
                    xref = img[0]
                    base_image = pdf_file.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # 使用 PIL 處理圖片
                    if image_ext == "jpx":
                        image = Image.open(io.BytesIO(image_bytes))
                        image_ext = "png"  # 轉換為 PNG 格式
                    else:
                        image = Image.open(io.BytesIO(image_bytes))

                    image_path = os.path.join(self.output_folder, f"image_page{page_index+1}_{img_index+1}.{image_ext}")
                    image.save(image_path)
                    self.images.append({"page_number": page_index + 1, "image_path": image_path})
                    logger.info(f"圖片已保存到: {image_path}")
        except Exception as e:
            logger.error(f"提取圖片時發生錯誤: {e}")

    def extract_tables(self):
        logger.info("提取表格內容...")
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_index, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    if tables:
                        for table_index, table in enumerate(tables):
                            csv_file = os.path.join(self.output_folder, f"table_page{page_index+1}_{table_index+1}.csv")
                            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                                writer = csv.writer(f)
                                for row in table:
                                    writer.writerow([str(cell) if cell else "" for cell in row])
                            self.tables.append({"page_number": page_index + 1, "csv_path": csv_file})
                            logger.info(f"表格已保存到: {csv_file}")
        except Exception as e:
            logger.error(f"提取表格時發生錯誤: {e}")

    def call_gpt_api(self, prompt, base64_data=None):
        headers = {
            "Authorization": f"Bearer {GPT_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        if base64_data:
            payload["messages"][0]["content"] = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_data}"}}
            ]

        try:
            response = requests.post(GPT_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"調用 GPT API 時發生錯誤: {e}")
            return None

    def process_tables_with_gpt(self):
        logger.info("使用 GPT 描述表格內容...")
        for table_info in self.tables:
            page_number = table_info["page_number"]
            csv_path = table_info["csv_path"]
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    csv_content = f.read()
                prompt = "請用描述的方式，去敘述表格中的內容，包括x軸對應y軸的一些內容，請將表格內所有資料都描述出來"
                gpt_result = self.call_gpt_api(prompt)
                if gpt_result:
                    for content in self.page_contents:
                        if content["page_number"] == page_number:
                            content["table_descriptions"].append(gpt_result)
                            break
            except Exception as e:
                logger.error(f"處理表格時發生錯誤: {e}")

    def process_images_with_gpt(self):
        logger.info("使用 GPT 描述圖片內容...")
        for image_info in self.images:
            page_number = image_info["page_number"]
            image_path = image_info["image_path"]
            try:
                with open(image_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode('utf-8')
                prompt = ("What information is in this image? The information should all be related "
                          "to the environment. Please do not include anything about other fields. Also, please observe carefully "
                          "and provide a detailed description of the content in the image. If there are tables or flowcharts, "
                          "please explain their contents in detail. Pay special attention to describing the relationships and "
                          "content of any text or numbers in the image without omitting any details. However, please note: "
                          "do not include any content unrelated to the image, assumptions, or introductory/concluding remarks. "
                          "Additionally, if there are meaningless patterns such as watermarks or small icons, please ignore them. "
                          "And please describe it in Traditional Chinese.")
                gpt_result = self.call_gpt_api(prompt, base64_image)
                if gpt_result:
                    for content in self.page_contents:
                        if content["page_number"] == page_number:
                            content["image_descriptions"].append(gpt_result)
                            break
            except Exception as e:
                logger.error(f"處理圖片時發生錯誤: {e}")

    def process(self):
        threads = []

        threads.append(threading.Thread(target=self.extract_text))
        threads.append(threading.Thread(target=self.extract_images))
        threads.append(threading.Thread(target=self.extract_tables))

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        #self.process_tables_with_gpt()
        self.process_images_with_gpt()

        # 保存最終內容到文本檔案
        final_output_file = os.path.join(self.output_folder, "final_output.txt")
        with open(final_output_file, "w", encoding="utf-8") as f:
            for content in self.page_contents:
                f.write(f"--- 第 {content['page_number']} 頁 ---\n")
                f.write(content['text'] + "\n")
                for description in content["table_descriptions"]:
                    f.write(f"表格描述: {description}\n")
                for description in content["image_descriptions"]:
                    f.write(f"圖片描述: {description}\n")
        logger.info(f"所有處理結果已保存到: {final_output_file}")



if __name__ == "__main__":
    pdf_path = "_output/test.pdf"  # PDF 路徑
    processor = PdfProcessor(pdf_path)
    processor.process()
