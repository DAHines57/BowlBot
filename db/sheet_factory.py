import os

from dotenv import load_dotenv

from sheets_handler import SheetHandler, get_sheet_handler


def get_handler_from_env() -> SheetHandler:
    """Workbook source for sync_db only (local Excel). The web app does not use this."""
    load_dotenv()
    path = os.environ.get("EXCEL_FILE_PATH", "Bowling-Friends League v5.xlsx")
    return get_sheet_handler("excel", file_path=path)
