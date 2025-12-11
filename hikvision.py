import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
from openpyxl import Workbook
import re

USERNAME = "admin"
PASSWORD = "insert_your_password"
TIMEOUT = 5

# ------------------------------------------------------
# READ IP LIST FROM ips.txt
# ------------------------------------------------------
def load_ips():
    try:
        with open("ips.txt", "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("ERROR: ips.txt not found!")
        return []

IPS = load_ips()

# ------------------------------------------------------
# XML helpers to get model/serial/firmware robustly
# ------------------------------------------------------
def safe_findtext(root, tags, ns=None):
    if ns:
        for t in tags:
            v = root.findtext(f".//ns:{t}", default=None, namespaces={"ns": ns})
            if v:
                return v
    else:
        for t in tags:
            v = root.findtext(f".//{t}")
            if v:
                return v

    for elem in root.iter():
        if elem.tag:
            name = elem.tag.split("}")[-1]
            if name.lower() in [x.lower() for x in tags]:
                return elem.text
    return None

def extract_from_raw_xml_text(raw, pattern):
    m = re.search(pattern, raw, re.IGNORECASE)
    return m.group(1).strip() if m else None

# ------------------------------------------------------
# FETCH DEVICE INFO
# ------------------------------------------------------
def get_device_info(ip):
    url = f"http://{ip}/ISAPI/System/deviceInfo"

    try:
        response = requests.get(
            url,
            auth=HTTPDigestAuth(USERNAME, PASSWORD),
            timeout=TIMEOUT,
            verify=False
        )

        if response.status_code == 401:
            return ["Unauthorized", "", ""]

        if response.status_code != 200:
            return [f"HTTP {response.status_code}", "", ""]

        raw = response.text

        # parse XML
        try:
            root = ET.fromstring(raw)
        except Exception:
            model = extract_from_raw_xml_text(raw, r"<(?:model|deviceModel)>([^<]+)</")
            serial = extract_from_raw_xml_text(raw, r"<serialNumber>([^<]+)</")
            firmware = extract_from_raw_xml_text(raw, r"<firmwareVersion>([^<]+)</")
            build = extract_from_raw_xml_text(raw, r"<firmwareReleasedDate>([^<]+)</")

            # >>> ADD YOUR CONCAT HERE <<<
            if firmware and build:
                firmware = f"{firmware} build {build}"

            return [
                model or "",
                serial or "",
                firmware or "",
            ]

        ns_url = "http://www.hikvision.com/ver20/XMLSchema"

        model = safe_findtext(root, ["model", "deviceModel"], ns=ns_url) or \
                safe_findtext(root, ["model", "deviceModel"])

        serial = safe_findtext(root, ["serialNumber", "serial"])
        firmware = safe_findtext(root, ["firmwareVersion", "softwareVersion"])
        build = safe_findtext(root, ["firmwareReleasedDate", "releasedDate"])

        # >>> ADD YOUR CONCAT HERE <<<
        if firmware and build:
            firmware = f"{firmware} build {build}"

        return [
            (model or "").strip(),
            (serial or "").strip(),
            (firmware or "").strip(),
        ]

    except requests.exceptions.Timeout:
        return ["Timeout", "", ""]
    except Exception as e:
        return [f"Error: {str(e)}", "", ""]

# ------------------------------------------------------
# MAIN EXECUTION
# ------------------------------------------------------
def main():
    if not IPS:
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Hikvision Scan"
    ws.append(["IP", "Model", "Serial Number", "Firmware"])

    print("\n===========================================================")
    print("        HIKVISION DEVICE SCANNER  (Model / SN / FW)")
    print("===========================================================\n")
    print(f"{'IP':<16}{'Model':<20}{'Serial Number':<32}{'Firmware'}")
    print("-" * 75)

    for ip in IPS:
        model, serial, firmware = get_device_info(ip)
        ws.append([ip, model, serial, firmware])
        print(f"{ip:<16}{model:<20}{serial:<32}{firmware}")

    out_file = "hikvision_devices.xlsx"
    wb.save(out_file)

    print("\nSaved → hikvision_devices.xlsx\n")

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    main()
