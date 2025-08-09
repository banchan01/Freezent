import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import urllib3
from dotenv import load_dotenv

# ===== .env 로드 =====
load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE_URL = "https://www.infostockdaily.co.kr"


def clean_text(tag):
    return tag.get_text(separator=" ", strip=True) if tag else "내용 없음"


# ===== 1. 크롤링 함수 =====
def crawl_articles_by_stock(stock_name: str, max_articles=10):
    articles = []
    page = 1
    skip_pattern = r"^\[\d{4}[^\]]+\]"
    encoded_name = quote(stock_name)

    while len(articles) < max_articles:
        print(
            f"[+] '{stock_name}' 검색, {page}페이지 요청 중... (현재 {len(articles)}/{max_articles}개)"
        )
        search_url = f"{BASE_URL}/news/articleList.html?sc_section_code=S1N17&view_type=sm&sc_word={encoded_name}&page={page}"

        try:
            res = requests.get(search_url, verify=False, timeout=10)
            res.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[!] 페이지 요청 실패: {e}")
            break

        soup = BeautifulSoup(res.text, "html.parser")
        article_blocks = soup.select("div.list-block")
        if not article_blocks:
            print("[-] 더 이상 기사 없음. 탐색 중단.")
            break

        for block in article_blocks:
            if len(articles) >= max_articles:
                break

            title_tag = block.select_one("div.list-titles a")
            if not title_tag:
                continue

            preview_title = title_tag.get_text(strip=True)
            if re.match(skip_pattern, preview_title):
                print(f"  [-] 제목 형식 불일치로 제외: {preview_title}")
                continue

            link = urljoin(BASE_URL, title_tag.get("href"))

            try:
                detail_res = requests.get(link, verify=False, timeout=10)
                detail_soup = BeautifulSoup(detail_res.text, "html.parser")

                full_title = clean_text(
                    detail_soup.select_one("div.article-head-title")
                )

                content_tag = detail_soup.select_one("div#article-view-content-div")

                if content_tag:
                    if tag_group_div := content_tag.select_one(".tag-group"):
                        tag_group_div.decompose()
                    if script_tag := content_tag.find("script"):
                        script_tag.decompose()
                    if copyright_div := content_tag.select_one(".view-copyright"):
                        copyright_div.decompose()
                    if editors_div := content_tag.select_one(".view-editors"):
                        editors_div.decompose()

                    p_tags = content_tag.find_all("p")
                    if p_tags:
                        p_tags[-1].decompose()

                content = clean_text(content_tag)

                date_text = "날짜 정보 없음"
                info_lis = detail_soup.select("div.info-text li")
                for li in info_lis:
                    if "최종수정" in li.get_text():
                        date_text = (
                            li.get_text(strip=True).replace("최종수정", "").strip()
                        )
                        break
                if date_text == "날짜 정보 없음":
                    for li in info_lis:
                        if "승인" in li.get_text():
                            date_text = (
                                li.get_text(strip=True).replace("승인", "").strip()
                            )
                            break

                articles.append(
                    {
                        "종목명": stock_name,
                        "제목": full_title,
                        "날짜": date_text,
                        "본문": content,
                        "링크": link,
                    }
                )
                print(f"  [+] 저장됨: {full_title}")

            except Exception as e:
                print(f"[!] 기사 크롤링 실패: {link} → {e}")

        page += 1

    return articles
