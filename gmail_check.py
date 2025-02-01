import os
import base64
import time
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from lxml import etree
from io import StringIO
import requests

# log settings
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "gmail_checker.log")

# check log directory
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - %(level)s - %(message)s",
  handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

# gmail api scope
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def authenticate_gmail():
  """ Gmail API 인증 """
  creds = None
  credentials_path = "credentials.json"
  token_path = "token.json"
  if os.path.exists(token_path):
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      try:
        creds.refresh(Request())
      except:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)
    else:
      flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
      creds = flow.run_local_server(port=0)
    with open(token_path, "w") as token:
        token.write(creds.to_json())
  return creds

def check_emails2(service, sender_email, download_path):
    """ 특정 발신자의 이메일 확인 및 첨부파일 다운로드. """
    try:
      logging.info("메일 확인 중...")
      results = service.users().messages().list(userId="me", q=f"from:{sender_email}").execute()
      messages = results.get("messages", [])

      if not messages:
        # logging.info("새로운 이메일이 없습니다.")
        return False

      for message in messages:
        msg = service.users().messages().get(userId="me", id=message["id"]).execute()
        payload = msg["payload"]
        headers = payload.get("headers", [])

        # for header in headers:
        #   if header["name"] == "Subject":
        #     logging.info(f"제목: {header['value']}")

        if "parts" in payload["body"]:
          for part in payload["body"]["parts"]:
            if part["filename"]:
              attachment_id = part["body"]["attachmentId"]
              attachment = service.users().messages().attachments().get(userId="me", messageId=message["id"], id=attachment_id).execute()
              data = base64.urlsafe_b64decode(
                  attachment["data"].encode("UTF-8")
              )
              file_path = os.path.join(download_path, part["filename"])
              with open(file_path, "wb") as f:
                f.write(data)
                logging.info(f"첨부파일 저장됨: {file_path}")

              return True
    except HttpError as error:
      logging.error(f"An error occurred: {error}")

    return False

def check_emails(service, sender_email, download_path, mode="attachment", search_query=""):
  """
  특정 발신자의 이메일을 확인하고 요청에 따라 첨부파일 다운로드 또는 HTML 본문 분석을 수행.
  
  Args:
      service: Gmail API 서비스 객체.
      sender_email: 확인할 발신자 이메일 주소.
      download_path: 첨부파일 저장 경로.
      mode: 작업 모드 ("attachment" 또는 "html").
  
  Returns:
      bool: 작업 성공 여부.
  """
  try:
    logging.info("📩 메일 확인 중...")

    query = f"from:{sender_email} label:inbox"

    if search_query:
      query += f" {search_query}"

    results = service.users().messages().list(userId="me", q=query).execute()
    messages = results.get("messages", [])

    if not messages:
      logging.info("✅ 조건에 맞는 이메일이 없습니다.")
      return False
    
    for message in messages:
      msg_id = message["id"]
      msg = service.users().messages().get(userId="me", id=message["id"]).execute()
      payload = msg["payload"]
      headers = payload.get("headers", [])

      for header in headers:
        if header["name"] == "Subject":
          logging.info(f"📌 제목: {header['value']}")

      if mode == "attachment":
        # 첨부파일 다운로드
        if "parts" in payload["body"]:
          for part in payload["body"]["parts"]:
            if part["filename"]:
              attachment_id = part["body"]["attachmentId"]
              attachment = service.users().messages().attachments().get(
                  userId="me", messageId=message["id"], id=attachment_id
              ).execute()
              data = base64.urlsafe_b64decode(
                attachment["data"].encode("UTF-8")
              )
              file_path = os.path.join(download_path, part["filename"])
              with open(file_path, "wb") as f:
                f.write(data)
                logging.info(f"🔗 첨부파일 저장됨: {file_path}")

              return True
      elif mode == "body":
        # 이메일 본문 다운로드
        html_body = None
        # HTML 본문 분석
        if payload.get("body") and "data" in payload["body"]:
          html_body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
        elif "parts" in payload:
          for part in payload["parts"]:
            if part["mimeType"] == "text/html" and "data" in part["body"]:
              html_body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
              break
        
        if not html_body:
          logging.info("⚠️ HTML 본문을 찾을 수 없습니다.")
          return False

        # HTML에서 XPath로 특정 버튼의 href 추출
        try:
          parser = etree.HTMLParser()
          tree = etree.parse(StringIO(html_body), parser)

          # XPath를 사용해 버튼의 href 속성 추출
          # XPath 예: 모든 <a> 태그 중 버튼과 관련된 조건을 설정
          hrefs = tree.xpath("//a[contains(@class, 'email-button') or contains(text(), 'Download my archive')]/@href")

          if not hrefs:
            logging.info("⚠️ 버튼 링크를 찾을 수 없습니다.")
            return False

          # 추출된 href 저장
          file_path = os.path.join(download_path, f"email_links.txt")
          with open(file_path, "w", encoding="utf-8") as f:
            for href in hrefs:
                f.write(href + "\n")
                logging.info(f"🔗 추출된 링크 저장됨: {href}")
        except Exception as e:
          logging.error(f"❌ HTML 파싱 중 오류 발생: {e}")

      try:
        service.users().messages().modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}).execute()
        logging.info(f"✅ 메일 ID {msg_id} → 읽음 처리됨")
      except HttpError as e:
        logging.error(f"❌ 읽음 처리 실패 (메일 ID: {msg_id}): {e}")

    return True
  except HttpError as error:
    logging.error(f"❌ API 오류 발생: {error}")
    return False

def download_file_from_link(link, download_path):
  """
  주어진 링크에서 파일을 다운로드하고 지정된 경로에 저장합니다.

  Args:
      link (str): 파일을 다운로드할 URL.
      download_path (str): 파일을 저장할 디렉토리 경로.

  Returns:
      str: 다운로드된 파일의 경로.
  """
  try:
    # 요청 보내기
    logging.info(f"다운로드 요청: {link}")
    response = requests.get(link, stream=True)  # 스트리밍 모드로 파일 다운로드
    response.raise_for_status()  # HTTP 오류 발생 시 예외 처리

    # 파일 이름 추출
    filename = link.split("/")[-1] or "downloaded_file"
    file_path = os.path.join(download_path, filename)

    # 파일 저장
    with open(file_path, "wb") as file:
      for chunk in response.iter_content(chunk_size=8192):  # 청크 단위로 읽기
        file.write(chunk)

    logging.info(f"파일 다운로드 완료: {file_path}")

    # TODO: 해당 파일 다운로드 받아서 압축 풀고, bookmarks 부분을 저장 필요

    return file_path
  except requests.exceptions.RequestException as e:
    logging.error(f"파일 다운로드 실패: {e}")
    return None

def process_links_and_download(links, download_path):
  """
  여러 링크를 순회하며 파일을 다운로드합니다.

  Args:
      links (list): 다운로드할 링크 목록.
      download_path (str): 파일을 저장할 디렉토리 경로.
  """
  if not os.path.exists(download_path):
    os.makedirs(download_path)

  for link in links:
    downloaded_file = download_file_from_link(link, download_path)
    if downloaded_file:
      logging.info(f"다운로드 성공: {downloaded_file}")
    else:
      logging.warning(f"다운로드 실패: {link}")

def main():
  sender_email = "noreply@medium.com"
  download_path = "downloads"
  interval = 1

  if not os.path.exists(download_path):
    os.makedirs(download_path)

  creds = authenticate_gmail()
  service = build("gmail", "v1", credentials=creds)

  while True:
    if check_emails(service, sender_email, download_path, mode="body", search_query="subject:'Medium download request' is:unread"):
      break
    else:
      logging.info(f"첨부파일이 있는 메일을 찾지 못했습니다. {interval} 분 후 다시 시도합니다.")
      time.sleep(60 * interval)

if __name__ == "__main__":
  main()
