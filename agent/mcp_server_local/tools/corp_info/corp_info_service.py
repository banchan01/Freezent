# mcp/tools/corp_info/corp_info_service.py
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional


def _find_dataset_dir(max_up: int = 6) -> Optional[str]:
    """
    현재 파일 기준으로 위로 올라가며 'dataset' 폴더가 있으면 그 경로를 반환.
    """
    d = os.path.abspath(os.path.dirname(__file__))
    for _ in range(max_up):
        # We are in mcp/tools/corp_info, so we need to go up 3 levels to find mcp/dataset
        d = os.path.dirname(d)
        candidate = os.path.join(d, "dataset")
        if os.path.isdir(candidate):
            return candidate
    return None


def get_corp_code_xml_path() -> str:
    """Locates the corpCode.zip file."""
    dataset_dir = _find_dataset_dir()
    if not dataset_dir:
        raise FileNotFoundError("Could not find the 'dataset' directory in the project structure.")
    return os.path.join(dataset_dir, "corpCode.zip")


def parse_corp_xml(xml_path: str) -> Optional[List[Dict]]:
    """XML 파일에서 기업 정보를 파싱합니다."""
    try:
        with zipfile.ZipFile(xml_path, "r") as zip_file:
            xml_files = [f for f in zip_file.namelist() if f.endswith(".xml")]
            if not xml_files:
                return None

            xml_content = zip_file.read(xml_files[0])
            root = ET.fromstring(xml_content)

            corp_list: List[Dict] = []
            for corp in root.findall("list"):
                corp_code = (corp.find("corp_code").text if corp.find("corp_code") is not None else "").strip()
                corp_name = (corp.find("corp_name").text if corp.find("corp_name") is not None else "").strip()
                stock_code = (corp.find("stock_code").text if corp.find("stock_code") is not None else "").strip()

                if corp_code and corp_name:
                    corp_list.append({
                        "corp_code": corp_code,
                        "corp_name": corp_name,
                        "stock_code": stock_code if stock_code else None,
                    })
            return corp_list
    except Exception as e:
        print(f"[corp_info_service] Error parsing XML: {e}")
        return None


def find_corp_info_by_name(stock_name: str) -> Dict[str, Optional[str]]:
    """Finds a corporation's info by its name from the local XML file."""
    if not stock_name:
        return {"error": "stock_name must be provided."}

    try:
        xml_path = get_corp_code_xml_path()
        if not os.path.exists(xml_path):
            return {"error": f"CORPCODE file not found at {xml_path}. Please ensure it has been downloaded."}
        
        corp_list = parse_corp_xml(xml_path)
        if not corp_list:
            return {"error": "Failed to parse corp code XML file."}

    except FileNotFoundError as e:
        return {"error": str(e)}

    # Find exact and partial matches
    exact_matches = [corp for corp in corp_list if corp["corp_name"] == stock_name and corp.get("stock_code")]
    partial_matches = [corp for corp in corp_list if stock_name in corp["corp_name"] and corp.get("stock_code")]

    if exact_matches:
        return exact_matches[0]
    if partial_matches:
        return partial_matches[0]
    
    return {"error": f"Could not find a listed company with name containing '{stock_name}'."}
