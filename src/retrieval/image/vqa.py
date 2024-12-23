import base64
import json
import os
import logging
import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class VqaProcessor:
    """
    負責處理圖片，直接調用 GPT-4o-mini API 進行圖像分析。
    """

    def __init__(self, gpt_api_url, gpt_api_key):
        self.gpt_api_url = gpt_api_url
        self.gpt_api_key = gpt_api_key
        logger.info(f"GPT API URL: {self.gpt_api_url}")

    def call_gpt_api(self, base64_image):

        headers = {
            "Authorization": f"Bearer {self.gpt_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What information is in this image? The information should all be related" 
                         "to the environment. Please do not include anything about other fields. Also, please observe carefully" 
                         "and provide a detailed description of the content in the image. If there are tables or flowcharts," 
                         "please explain their contents in detail. Pay special attention to describing the relationships and" 
                         "content of any text or numbers in the image without omitting any details. However, please note:" 
                         "do not include any content unrelated to the image, assumptions, or introductory/concluding remarks." 
                         "Additionally, if there are meaningless patterns such as watermarks or small icons, please ignore them." 
                         "And please describe it in Traditional Chinese."},
                         #這張圖片中有什麼信息？裡面的訊息都跟環境相關，請不要提到關於其他領域的東西，另外，請仔細觀察並詳細描述圖片中的內容。如果圖片中包含表格或流程圖，請詳細說明它們的內容。請特別注意，需要描述圖片中的文本或數字之間的關係和內容，不要遺漏任何細節。然而，請注意：不要包括與圖片無關的內容、假設或開頭和結尾的語句。此外，如果遇到一些無意義的圖案，例如水印或小圖示，請直接忽略。請用繁體中文描述。
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            "max_tokens": 1000
        }

        try:
            response = requests.post(self.gpt_api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"調用 GPT API 時發生錯誤: {e}")
            return None

    def process_image(self, image_path):
        #處理單個圖片並輸出結果
        if not os.path.exists(image_path):
            logger.error(f"圖片不存在：{image_path}")
            return None

        with open(image_path, "rb") as fp:
            base64_image = base64.b64encode(fp.read()).decode('utf-8')
        #logger.info(f"圖片已轉為 base64：{image_path}")

        # 調用 GPT API 進行圖像分析
        analysis_result = self.call_gpt_api(base64_image)

        if not analysis_result:
            logger.error(f"無法獲取 GPT 的分析結果：{image_path}")
            return None

        logger.info(f"圖片分析結果：{analysis_result}")
        return f"圖片 {os.path.basename(image_path)} 的內容：\n{analysis_result}\n"

    def process_all_images(self, input_folder, output_file):
        #批量處理資料夾中的所有圖片，並將結果保存到指定檔案

        if not os.path.exists(input_folder):
            logger.error(f"資料夾不存在：{input_folder}")
            return

        results = []
        for file_name in sorted(os.listdir(input_folder)):  # 按文件名排序
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):  # 僅處理圖片文件
                image_path = os.path.join(input_folder, file_name)
                logger.info(f"處理圖片：{image_path}")
                response = self.process_image(image_path)
                if response:
                    results.append(response)

        # 保存結果到檔案
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n\n".join(results))
            logger.info(f"所有圖片分析結果已保存到：{output_file}")
        except Exception as e:
            logger.error(f"保存處理結果時發生錯誤：{e}")


# 主程式
if __name__ == "__main__":

    GPT_API_URL = "https://api.openai.com/v1/chat/completions" 
    GPT_API_KEY = ""  # 替換為您的 GPT API 密鑰
    # 設定圖片資料夾與輸出檔案
    input_folder = "../_output"  # 圖片存放的資料夾
    output_file = "../_output/image_analysis.txt"  # 結果輸出的檔案
    # 確保輸出資料夾存在
    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))

    processor = VqaProcessor(GPT_API_URL, GPT_API_KEY)
    processor.process_all_images(input_folder, output_file)





        