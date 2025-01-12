import os
import requests
import time
from dotenv import load_dotenv
import glob
from lxml import etree
import json

load_dotenv()

NOTION_KEY = os.environ.get("NOTION_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
HEADERS = {
    "Authorization": f"Bearer {NOTION_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


# ✅ 안전한 데이터 접근 함수
def safe_get(data, keys, default=""):
    """
    다중 키를 안전하게 탐색하여 값을 반환합니다.
    """
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, {})
        elif isinstance(data, list):
            try:
                data = data[key]
            except (IndexError, TypeError):
                return default
        else:
            return default
    return data if data else default


def paginate_notion_api(url, payload=None):
    """
    Notion API의 페이지네이션을 처리하는 공통 함수.

    :param url: API 호출 URL
    :param payload: 요청에 사용할 추가 데이터 (기본값: None)
    :return: 페이지네이션을 통해 수집된 모든 항목의 리스트
    """
    all_results = []
    next_cursor = None  # 페이지네이션 커서

    while True:
        current_payload = payload.copy() if payload else {}
        if next_cursor:
            current_payload["start_cursor"] = next_cursor

        response = requests.post(url, headers=HEADERS, json=current_payload)

        if response.status_code != 200:
            print(f"❌ Failed to fetch data: {response.json()}")
            break

        data = response.json()
        results = data.get("results", [])
        all_results.extend(results)

        print(f"✅ Fetched {len(results)} items (Total: {len(all_results)})")

        if data.get("has_more", False):
            next_cursor = data.get("next_cursor")
        else:
            break

    return all_results


# ✅ Notion 데이터베이스에서 항목 가져오기 (페이지네이션 지원)
def fetch_notion_database():
    """
    Notion 데이터베이스에서 항목을 모두 가져와 old_list로 반환합니다.
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"

    results = paginate_notion_api(url)

    old_list = []

    # ✅ results에서 항목 추출
    for result in results:
        properties = result.get("properties", {})
        item_id = result.get("id", "")
        item_url = safe_get(properties, ["url", "url"], "")
        item_title = safe_get(properties, ["title", "title", 0, "text", "content"], "")
        item_time = safe_get(
            properties, ["time", "rich_text", 0, "text", "content"], ""
        )

        if (
            item_url or item_title
        ):  # and 로 하 되면 어느 한쪽이 null 일때는 old_list 에 반영안됨
            old_list.append(
                {
                    "id": item_id,
                    "url": item_url,
                    "title": item_title,
                    "time": item_time,
                }
            )

    print(f"✅ Fetched {len(results)} items (Total: {len(old_list)})")

    print(f"✅ Completed fetching all items from Notion (Total: {len(old_list)})")
    return old_list


# ✅ Notion에 항목 추가
def add_to_notion_database(item):
    """
    Notion 데이터베이스에 항목을 추가합니다.
    """
    url = "https://api.notion.com/v1/pages"

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "title": {"title": [{"text": {"content": item["title"]}}]},
            "url": {"url": item["url"]},
            "time": {"rich_text": [{"text": {"content": item.get("time", "")}}]},
        },
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code == 200:
        print(f"✅ Added to Notion: {item['title']}")
    else:
        print(f"❌ Failed to add to Notion: {item['title']}")
        print(response.json())


# ✅ Notion 항목 삭제
def delete_from_notion_database(item_id):
    """
    Notion 데이터베이스 항목을 삭제합니다.
    """
    url = f"https://api.notion.com/v1/pages/{item_id}"
    payload = {"archived": True}

    response = requests.patch(url, headers=HEADERS, json=payload)
    if response.status_code == 200:
        print(f"✅ Removed from Notion: {item_id}")
    else:
        print(f"❌ Failed to remove from Notion: {item_id}")
        print(response.json())


def delete_all_notion_items():
    """
    Notion 데이터베이스의 모든 항목을 제거합니다.
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    results = paginate_notion_api(url)

    for result in results:
        item_id = result.get("id", "")
        if item_id:
            delete_from_notion_database(item_id)
            time.sleep(0.2)  # API Rate Limit 방지를 위해 잠시 대기

    print("✅ All items in the Notion database have been deleted.")


# ✅ Notion 데이터베이스 업데이트
def update_notion_database(added, removed):
    """
    Notion 데이터베이스를 업데이트합니다.
    - 추가된 항목은 추가
    - 삭제된 항목은 삭제
    """
    for item in added:
        add_to_notion_database(item)

    for item in removed:
        delete_from_notion_database(item["id"])


def check_item_exists_in_notion(property_name, value):
    """
    Notion 데이터베이스에서 특정 속성(property_name)의 값(value)이 존재하는지 확인합니다.

    :param property_name: 필터링할 속성 이름 (예: 'URL', 'title')
    :param value: 필터링할 값 (예: 특정 URL, 제목)
    :return: 존재 여부 (True/False)
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"

    payload = {
        "filter": {
            "property": property_name,
            property_name.lower(): {"equals": value},  # 속성 타입에 따라 필터 조건 결정
        }
    }

    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        print(f"❌ Failed to check item existence: {response.json()}")
        return False

    data = response.json()
    results = data.get("results", [])

    if results:
        print(f"✅ Item exists with {property_name} = {value}")
        return True
    else:
        print(f"❌ Item does not exist with {property_name} = {value}")
        return False


# ✅ HTML 파일에서 URL과 제목을 추출하는 함수 (XPath 사용)
def extract_links_from_html(file_path):
    """
    XPath를 사용하여 HTML 파일에서 <body> → <section> → <ul> → <li> → <a> 구조로 URL과 제목을 추출합니다.
    """
    links = []  # 결과를 저장할 리스트

    # HTML 파일 읽기
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
        parser = etree.HTMLParser()
        tree = etree.fromstring(content, parser)  # lxml을 사용해 HTML 파싱

        # XPath를 사용해 a 태그 찾기
        li_tags = tree.xpath("//body/section/ul/li")

        for li in li_tags:
            a_tag = li.xpath('./a[@class="h-cite"]')
            time_tag = li.xpath('./time[@class="dt-published"]')

            url = a_tag[0].get("href") if a_tag else None  # href 속성 추출
            title = (
                a_tag[0].text.strip() if a_tag and a_tag[0].text else None
            )  # 태그 텍스트 추출 (공백 제거)
            time = time_tag[0].text.strip() if time_tag and time_tag[0].text else None

            if url and title:
                links.append({"url": url, "title": title, "time": time})

    return links


# ✅ 여러 HTML 파일에서 URL과 제목을 추출
def process_multiple_html_files(directory, file_pattern="bookmarks-*.html"):
    """
    주어진 디렉터리에서 여러 HTML 파일을 읽고 URL과 제목을 추출합니다.
    """
    all_links = []  # 모든 링크를 저장할 리스트

    # 파일 패턴에 맞는 모든 HTML 파일 찾기
    file_paths = glob.glob(os.path.join(directory, file_pattern))

    for file_path in file_paths:
        print(f"📄 Processing: {file_path}")
        links = extract_links_from_html(file_path)
        all_links.extend(links)  # 추출된 링크를 전체 리스트에 추가

    with open("all_links.json", "w", encoding="utf-8") as jsonfile:
        json.dump(all_links, jsonfile, indent=2, ensure_ascii=False)

    return all_links


# ✅ 글로벌 비교 로직
def global_diff_update(old_list, new_list):
    """
    old_list(Notion DB)와 new_list(로컬 데이터)를 비교하여 added, removed, unchanged를 도출합니다.
    """
    old_map = {item["url"]: item for item in old_list}
    new_map = {item["url"]: item for item in new_list}

    added = [item for url, item in new_map.items() if url not in old_map]
    removed = [item for url, item in old_map.items() if url not in new_map]
    unchanged = [item for url, item in new_map.items() if url in old_map]

    print(
        f"✅ Comparison complete: Added: {len(added)}, Removed: {len(removed)}, Unchanged: {len(unchanged)}"
    )

    return added, removed, unchanged


# ✅ 메인 실행
if __name__ == "__main__":
    # HTML 파일들이 저장된 디렉터리 경로 설정
    input_directory = "./bookmarks"

    # ✅ Step 1: Notion 데이터베이스에서 old_list 가져오기
    old_list = fetch_notion_database()

    # ✅ Step 2: 로컬 HTML 파일에서 new_list 가져오기
    new_list = process_multiple_html_files(input_directory)
    print(f"✅ Loaded {len(new_list)} items from bookmarks.")

    # ✅ Step 3: 글로벌 비교 수행
    added, removed, unchanged = global_diff_update(old_list, new_list)

    # ✅ Step 4: Notion 업데이트 수행
    update_notion_database(added, removed)

    # ✅ check item
    # url_to_check = "https://medium.com/p/building-robust-api-clients-with-refit-rest-library-in-c-43862c4cad76"
    # item_exists = check_item_exists_in_notion("url", url_to_check)
    # if item_exists:
    #     print("✅ The item already exists in the database.")
    # else:
    #     print("❌ The item does not exist. You can safely add it.")

    print("\n🎯 Database synchronization complete!")
