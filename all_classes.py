# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "beautifulsoup4>=4.12.0",
#     "requests>=2.31.0",
#     "tqdm>=4.66.1",
#     "urllib3>=2.1.0",
#     "lxml>=4.9.3",
# ]
# ///
# uv run all_classes.py
# Takes about an hour
import requests  # type: ignore
import time
import re
import json
from datetime import datetime
from urllib3.util.retry import Retry  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
from tqdm import tqdm  # type: ignore
import os

# --- Configuration ---
BASE_URL_TEMPLATE = "https://www.mfri.org/course/msfs/FIRE/101/{s_code}/{year}/"
JSON_OUTPUT_FILE = "mfri_firefigher_I_old_and_new_courses.json"
USER_AGENT = "MFRI Course Data Collector Bot/1.3 (Python Script)"

# Regex to identify an active page by a specific date pattern "Start: Month Day, Year"
ACTIVE_CONTENT_REGEX = re.compile(
    r"Start:\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
)
# Generic search page URL substring to identify unwanted redirects
GENERIC_SEARCH_SUBSTRING = "/course-search/"


# --- Helper Functions for JSON and Dates ---
def format_date_mdy(date_str_month_day_year):
    if not date_str_month_day_year or date_str_month_day_year == "N/A":
        return "N/A"
    try:
        cleaned_date_str = re.sub(r"\s*,\s*", ", ", date_str_month_day_year.strip())
        dt_obj = datetime.strptime(cleaned_date_str, "%B %d, %Y")
        return dt_obj.strftime("%m-%d-%Y")
    except ValueError:
        # Try another common format if the first fails, e.g., MM-DD-YYYY already
        try:
            dt_obj = datetime.strptime(cleaned_date_str, "%m-%d-%Y")
            return dt_obj.strftime("%m-%d-%Y")  # Already in correct format
        except ValueError:
            # print(f"Warning: Could not parse date string: '{date_str_month_day_year}'")
            return date_str_month_day_year


def load_existing_data(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_data(filename, data_list):
    sorted_data = sorted(
        data_list, key=lambda x: (x.get("courseId") is None, x.get("courseId", ""))
    )
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=4, ensure_ascii=False)


def get_text_from_element_after_heading(
    soup, heading_text_regex, next_tag="p", next_class="intro", return_text_only=True
):
    heading = soup.find(["h4", "h5"], string=heading_text_regex)  # Allow h4 or h5
    if heading:
        element = heading.find_next_sibling(next_tag, class_=next_class)
        if element:
            if return_text_only:
                # Consolidate text, handling <br> by replacing with newlines then joining
                text_parts = []
                for content in element.contents:
                    if isinstance(content, str):
                        text_parts.append(content.strip())
                    elif content.name == "br":
                        text_parts.append("\n")  # Add newline for br
                    elif hasattr(content, "get_text"):
                        text_parts.append(content.get_text(strip=True))

                full_text = " ".join(
                    line.strip()
                    for line in " ".join(text_parts).splitlines()
                    if line.strip()
                )
                return full_text.replace("\xa0", " ")  # Clean non-breaking spaces
            return element  # Return the tag itself
    return None


# --- Core Parsing Logic for INDIVIDUAL SXXX/YYYY pages ---
def parse_individual_course_page_details(html_content, course_url, locations_lookup):
    soup = BeautifulSoup(html_content, "lxml")
    # Initialize details with all fields from the target structure
    details = {
        "courseId": "N/A",
        "courseUrl": course_url,  # Added courseUrl, using the passed-in URL
        "registerLink": "N/A",
        "startDate": "N/A",
        "endDate": "N/A",
        "firstClassTime": "N/A",
        "days": "N/A",
        "registrationOpens": "N/A",
        "registrationCloses": "N/A",
        "location": "N/A",
        "instructionalHours": "N/A",  # Added instructionalHours
        "coordinateBy": "N/A",
        "contact": "N/A",
        "locationUrlId": None,
        "locationRegionId": None,
        "locationServedBy": None,
        "locationServedByUrl": None,
        "locationWebsiteAddress": None,
        "locationFormattedAddress": None,
        "locationLatitudeLongitude": None,
        "locationDisplayName": None,
        "locationGoogleMapsUrl": None,
        "locationGoogleMapsDirectionsUrl": None,
        "currentDate": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),  # Match target format
    }

    # 1. Course ID (Log Number) & Title
    course_title_h4 = soup.find("h4", class_=re.compile(r"red bold uppercase"))

    log_number_p_text = None
    # Find the <p class="intro"> that contains "Log Number:"
    # This is often after the main course title h4
    if course_title_h4:
        p_intro_candidate = course_title_h4.find_next_sibling(
            "p", class_="intro"
        )  # This is the BeautifulSoup tag
        if p_intro_candidate and "Log Number:" in p_intro_candidate.get_text():
            log_number_p_text = p_intro_candidate.get_text(separator="\n", strip=True)

    if not log_number_p_text:  # Fallback search if not immediately after title
        all_intro_p = soup.find_all("p", class_="intro")
        for p_tag in all_intro_p:
            if "Log Number:" in p_tag.get_text():
                log_number_p_text = p_tag.get_text(
                    separator="\n", strip=True
                )  # This is the text from the fallback
                break

    if log_number_p_text:
        # Extract Instructional Hours first if present in this paragraph
        hours_match_in_intro = re.search(
            r"Instructional Hours:\s*([\d\.]+)", log_number_p_text, re.IGNORECASE
        )
        if hours_match_in_intro:
            details["instructionalHours"] = hours_match_in_intro.group(1).strip()

        # Then extract Log Number
        log_match = re.search(
            r"Log Number:\s*([A-Z0-9\-S]+)", log_number_p_text
        )  # Include S in regex for SXXX
        details["courseId"] = log_match.group(1).strip() if log_match else "N/A"

    else:
        details["courseId"] = "N/A"

    if details["courseId"] == "N/A":
        print(
            f"  -> CRITICAL: Could not parse Course ID (Log Number) from {course_url}"
        )
        return None  # Essential field

    # 2. Register Link
    register_a = soup.find(
        "a", string=re.compile(r"^\s*Register\s*$", re.IGNORECASE), href=True
    )
    if register_a:
        details["registerLink"] = requests.compat.urljoin(
            course_url, register_a["href"]
        )  # Make URL absolute
    else:  # Fallback for links that might be structured differently, e.g. within a button-like div
        register_container = soup.find(
            lambda tag: tag.name == "h5" and "Register" in tag.get_text(strip=True)
        )
        if register_container and register_container.find("a", href=True):
            details["registerLink"] = requests.compat.urljoin(
                course_url, register_container.find("a")["href"]
            )
        else:
            details["registerLink"] = "N/A"

    # 3. Dates (Start, End) & First Class Time
    date_section_text = get_text_from_element_after_heading(
        soup, re.compile(r"^\s*Date:\s*$", re.IGNORECASE)
    )
    start_date_raw, end_date_raw = "N/A", "N/A"
    first_session_start_time, first_session_end_time = "N/A", "N/A"

    if date_section_text:
        start_match = re.search(
            r"Start:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", date_section_text, re.IGNORECASE
        )
        start_date_raw = start_match.group(1).strip() if start_match else "N/A"

        end_match = re.search(
            r"End:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", date_section_text, re.IGNORECASE
        )
        end_date_raw = end_match.group(1).strip() if end_match else "N/A"

        fsst_match = re.search(
            r"First Session Start Time:\s*(\d{1,2}:\d{2})",
            date_section_text,
            re.IGNORECASE,
        )
        first_session_start_time = fsst_match.group(1).strip() if fsst_match else "N/A"

        # End Time typically follows Start Time on the same "line" or next in text
        fset_match = re.search(
            r"(?:First Session Start Time:\s*\d{1,2}:\d{2}\s*(?:to|-)?\s*)?End Time:\s*(\d{1,2}:\d{2})",
            date_section_text,
            re.IGNORECASE,
        )
        first_session_end_time = (
            fset_match.group(1).strip()
            if fset_match and first_session_start_time != "N/A"
            else "N/A"
        )
        if (
            first_session_end_time == "N/A" and first_session_start_time != "N/A"
        ):  # If only start time and "End Time: HH:MM" is separate
            simple_end_time_match = re.search(
                r"End Time:\s*(\d{1,2}:\d{2})",
                date_section_text.split("First Session Start Time:", 1)[-1]
                if "First Session Start Time:" in date_section_text
                else date_section_text,
            )
            if simple_end_time_match:
                first_session_end_time = simple_end_time_match.group(1).strip()

    details["startDate"] = format_date_mdy(start_date_raw)
    details["endDate"] = format_date_mdy(end_date_raw)

    if first_session_start_time != "N/A" and first_session_end_time != "N/A":
        details["firstClassTime"] = (
            f"{first_session_start_time} - {first_session_end_time}"
        )
    elif first_session_start_time != "N/A":
        details["firstClassTime"] = first_session_start_time
    else:
        details["firstClassTime"] = "N/A"

    # 4. Days (Often under "Days and Times:" or sometimes inferred if not explicitly labeled)
    days_section_text = get_text_from_element_after_heading(
        soup, re.compile(r"^\s*Days and Times:\s*$", re.IGNORECASE)
    )
    if days_section_text:
        # The day string is usually the first significant part before times.
        # Example: "Mondays, Tuesdays, Wednesdays 18:30-22:30"
        # Or: "Mondays, Tuesdays, Wednesdays\n18:30-22:30"
        day_time_parts = days_section_text.split(
            "\n"
        )  # Split by explicit newlines first
        if not day_time_parts:
            day_time_parts = [days_section_text]

        potential_days_str = day_time_parts[0].strip()
        # Remove trailing time if it's on the same line
        potential_days_str = re.sub(
            r"\s+\d{1,2}:\d{2}.*$", "", potential_days_str
        ).strip()
        details["days"] = (
            potential_days_str
            if any(
                d.lower() in potential_days_str.lower()
                for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            )
            else "N/A"
        )

        # Try to get class time from here if not found in "Date:"
        if details.get("firstClassTime", "N/A") == "N/A":
            time_match = re.search(
                r"(\d{1,2}:\d{2}\s*(?:-|to)\s*\d{1,2}:\d{2})", days_section_text
            )
            if time_match:
                details["firstClassTime"] = time_match.group(1).strip()
            else:  # single time
                time_match_single = re.search(r"(\d{1,2}:\d{2})", days_section_text)
                if time_match_single:
                    details["firstClassTime"] = time_match_single.group(1).strip()

    elif (
        "days" not in details or details["days"] == "N/A"
    ):  # If no "Days and Times" heading
        details["days"] = "N/A"  # Could try to infer from "Date:" section if complex

    # 5. Registration Dates
    reg_section_text = get_text_from_element_after_heading(
        soup, re.compile(r"^\s*Registration:\s*$", re.IGNORECASE)
    )
    reg_opens_raw, reg_closes_raw = "N/A", "N/A"
    if reg_section_text:
        opens_match = re.search(
            r"Registration Opens:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{2}-\d{2}-\d{4})",
            reg_section_text,
            re.IGNORECASE,
        )
        reg_opens_raw = opens_match.group(1).strip() if opens_match else "N/A"

        closes_match = re.search(
            r"Registration Closes:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{2}-\d{2}-\d{4})",
            reg_section_text,
            re.IGNORECASE,
        )
        reg_closes_raw = closes_match.group(1).strip() if closes_match else "N/A"

    details["registrationOpens"] = format_date_mdy(reg_opens_raw)
    details["registrationCloses"] = format_date_mdy(reg_closes_raw)

    # 6. Location
    location_text = get_text_from_element_after_heading(
        soup, re.compile(r"^\s*Location:\s*$", re.IGNORECASE)
    )
    details["location"] = location_text.strip() if location_text else "N/A"
    if (
        details["location"] == "N/A"
    ):  # Try to find location if it was not under specific h4
        loc_p_alt = soup.find(
            "p", class_="intro", string=re.compile(r"Location:", re.IGNORECASE)
        )
        if loc_p_alt:
            loc_text_alt = loc_p_alt.get_text(separator=" ", strip=True)
            loc_text_alt = loc_text_alt.replace("Location:", "").strip()
            details["location"] = loc_text_alt

    # --- Add data from mfri_locations.json ---
    course_location_name = details.get("location")
    best_match_loc_data = None
    longest_match_len = 0

    if course_location_name and course_location_name != "N/A":
        # Iterate through the canonical location names from mfri_locations.json
        for mfri_loc_name_key, mfri_loc_data_value in locations_lookup.items():
            # Check if the canonical name is a substring of the scraped course location
            if mfri_loc_name_key in course_location_name:
                if len(mfri_loc_name_key) > longest_match_len:
                    longest_match_len = len(mfri_loc_name_key)
                    best_match_loc_data = mfri_loc_data_value

    if best_match_loc_data:
        details["locationUrlId"] = best_match_loc_data.get("urlId")
        details["locationRegionId"] = best_match_loc_data.get("id")
        details["locationServedBy"] = best_match_loc_data.get("servedBy")
        details["locationServedByUrl"] = best_match_loc_data.get("servedByUrl")
        details["locationWebsiteAddress"] = best_match_loc_data.get("websiteAddress")
        details["locationFormattedAddress"] = best_match_loc_data.get(
            "formattedAddress"
        )
        details["locationLatitudeLongitude"] = best_match_loc_data.get(
            "locationLatitudeLongitude"
        )
        details["locationDisplayName"] = best_match_loc_data.get("displayName")
        details["locationGoogleMapsUrl"] = best_match_loc_data.get("googleMapsUrl")
        details["locationGoogleMapsDirectionsUrl"] = best_match_loc_data.get(
            "googleMapsDirectionsUrl"
        )
    elif course_location_name and course_location_name != "N/A":
        print(
            f"    -> Note: Location '{course_location_name}' for course '{details.get('courseId', 'N/A')}' not found in mfri_locations.json with substring match."
        )

    # 7. Coordinated By and Contact
    coord_h5_tag = soup.find(  # Renamed to avoid conflict with coord_h5 in classes.py
        "h5",
        class_="mt-2 body-color",
        string=re.compile(r"Coordinated by:", re.IGNORECASE),
    )
    coord_by_text, contact_email = "N/A", "N/A"
    if coord_h5_tag:
        # Extract coordinator name (often in an <a> tag or plain text after "Coordinated by:")
        coord_a = coord_h5_tag.find(
            "a", class_="intro-item", href=re.compile(r"/office/")
        )
        if coord_a:
            raw_office_name = coord_a.get_text(strip=True)
            coord_by_text = re.sub(
                r"^(the\s+MFRI\s+)?|(\s+Office|\s+Regional\s+Training\s+Center)?$",
                "",
                raw_office_name,
                flags=re.IGNORECASE,
            ).strip()
        else:  # Try to get text after "Coordinated by:" up to "If you have any questions"
            coord_text_match = re.search(
                r"Coordinated by:\s*(.*?)(?:\s*\.\s*If you have any questions|\s*If you have any questions|$)",
                coord_h5_tag.get_text(separator=" ", strip=True),
                re.IGNORECASE,
            )
            if coord_text_match:
                coord_by_text = re.sub(
                    r"^(the\s+MFRI\s+)?|(\s+Office|\s+Regional\s+Training\s+Center)?$",
                    "",
                    coord_text_match.group(1),
                    flags=re.IGNORECASE,
                ).strip()

        # Extract contact email (usually in a mailto: link)
        email_a = coord_h5_tag.find(
            "a", class_="intro-item", href=re.compile(r"mailto:")
        )
        if email_a and email_a.has_attr("href"):
            contact_email = email_a["href"].replace("mailto:", "").strip()
        elif email_a:
            contact_email = email_a.get_text(
                strip=True
            )  # Fallback if href is missing but text is email-like

    details["coordinateBy"] = coord_by_text if coord_by_text else "N/A"
    details["contact"] = contact_email if contact_email else "N/A"

    # currentDate is already set during initialization to the correct format
    return details


# --- Link Checking and Main Iteration ---
def is_page_active_candidate(url_to_check, session):
    original_s_code = url_to_check.rstrip("/").split("/")[-2]
    original_year = url_to_check.rstrip("/").split("/")[-1]

    try:
        response = session.get(url_to_check, timeout=20, allow_redirects=True)
        final_url = response.url
        page_content = response.text

        if response.status_code != 200:
            return None, None

        if (
            GENERIC_SEARCH_SUBSTRING in final_url
            and BASE_URL_TEMPLATE.split("/{s_code}/")[0] in url_to_check
            and GENERIC_SEARCH_SUBSTRING not in url_to_check
        ):
            return None, None  # Redirected to generic search

        # Ensure final URL still pertains to the SXXX/YYYY structure we intended.
        # This is a bit loose as the base URL can change, e.g. /course/msfs/ -> /programs/msfs/
        # Key is that SXXX and YYYY are still there.
        if not (original_s_code in final_url and original_year in final_url):
            # print(f"  -> Final URL {final_url} mismatch for {original_s_code}/{original_year} from {url_to_check}.")
            return None, None

        if ACTIVE_CONTENT_REGEX.search(page_content):
            return page_content, final_url  # It's an active candidate
        else:
            return None, None  # No "Start: Month Day, Year" pattern

    except requests.exceptions.Timeout:
        print(f"  -> Timeout for {url_to_check}")
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"  -> Error for {url_to_check}: {e}")
        return None, None


def scrape_mfri_courses(s_range_start=0, s_range_end=1000, years_list=None):
    if years_list is None:
        current_yr = datetime.now().year
        years_list = range(
            current_yr - 1, current_yr + 3
        )  # Default: last year, current, next 2

    all_course_data_dict = {
        course["courseId"]: course
        for course in load_existing_data(JSON_OUTPUT_FILE)
        if course.get("courseId")
    }

    # Load mfri_locations.json to create a lookup table
    locations_json_path = "mfri_locations.json"
    locations_lookup = {}
    if os.path.exists(locations_json_path):
        try:
            with open(locations_json_path, "r", encoding="utf-8") as f_loc:
                mfri_locations_list = json.load(f_loc)
            # Create a lookup dictionary by location name.
            # If multiple entries have the same location name, this will use the first one encountered.
            for loc_data in mfri_locations_list:
                loc_name = loc_data.get("location")
                if (
                    loc_name and loc_name not in locations_lookup
                ):  # Use first occurrence
                    locations_lookup[loc_name] = loc_data
            print(
                f"Successfully loaded {len(locations_lookup)} unique locations from {locations_json_path} for lookup."
            )
        except Exception as e:
            print(
                f"Error loading or processing {locations_json_path}: {e}. Location details will not be added."
            )
    else:
        print(
            f"Warning: {locations_json_path} not found. Location details will not be added to courses."
        )

    print(f"Scanning S-codes from S{s_range_start:03d} to S{s_range_end - 1:03d}")
    print(f"Scanning years: {list(years_list)}")

    headers = {"User-Agent": USER_AGENT}
    new_courses_found_count = 0
    updated_courses_count = 0

    total_iterations = (s_range_end - s_range_start) * len(years_list)

    with tqdm(total=total_iterations, desc="Scanning MFRI Courses", unit="url") as pbar:
        with requests.Session() as session:
            session.headers.update(headers)
            retry_strategy = Retry(
                total=3,  # Total number of retries
                backoff_factor=1,  # Wait 1s, 2s, 4s between retries
                status_forcelist=[
                    429,
                    500,
                    502,
                    503,
                    504,
                ],  # Retry on these HTTP status codes
                allowed_methods=["HEAD", "GET", "OPTIONS"],  # Retry for these methods
                connect=5,  # Number of retries for connection-related errors (like DNS)
                read=3,  # Number of retries for read-related errors
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            for s_num in range(s_range_start, s_range_end):
                s_code = f"S{s_num:03d}"
                for year in years_list:
                    pbar.set_postfix_str(f"Current: S{s_code}/{year}", refresh=True)
                    url_to_check = BASE_URL_TEMPLATE.format(s_code=s_code, year=year)

                    page_content, final_url = is_page_active_candidate(
                        url_to_check, session
                    )

                    if page_content and final_url:
                        print(f"  -> ACTIVE: {final_url}. Parsing...")
                        # Use the parser for INDIVIDUAL course pages
                        course_details = parse_individual_course_page_details(
                            page_content,
                            final_url,
                            locations_lookup,  # Pass locations_lookup
                        )

                        if course_details and course_details.get("courseId") != "N/A":
                            course_id = course_details["courseId"]
                            # ADDED CHECK: Skip if courseId does not start with "FIRE-101"
                            if not course_id.startswith("FIRE-101"):
                                print(
                                    f"  INFO: Skipping course {course_id} from {final_url} as it does not start with 'FIRE-101'."
                                )
                            else:  # Original logic for FIRE-101 courses
                                if course_id not in all_course_data_dict:
                                    all_course_data_dict[course_id] = course_details
                                    print(
                                        f"  SUCCESS: Added NEW FIRE-101 course {course_id} from {final_url}"
                                    )
                                    new_courses_found_count += 1
                                else:
                                    # Update existing entry if different, or just confirm
                                    # For simplicity, we'll overwrite. Could add smarter diffing.
                                    all_course_data_dict[course_id] = course_details
                                    print(
                                        f"  SUCCESS: UPDATED/Confirmed FIRE-101 course {course_id} from {final_url}"
                                    )
                                    updated_courses_count += 1  # Count as updated even if same, means it's still active

                                # Save every time an active FIRE-101 course is processed
                                save_data(
                                    JSON_OUTPUT_FILE,
                                    list(all_course_data_dict.values()),
                                )

                        elif course_details:  # Parsed but courseId was "N/A" or missing
                            print(
                                f"  WARN: No Course ID (got '{course_details.get('courseId', 'Not Found')}') from {final_url}. Not saved."
                            )
                        else:  # Failed to parse anything meaningful
                            print(
                                f"  INFO: Failed to parse details from {final_url} (active candidate)."
                            )
                    else:
                        pass  # tqdm will show progress, no need to print for inactive

                    time.sleep(0.5)  # Be polite
                    pbar.update(1)

    # Final save
    save_data(JSON_OUTPUT_FILE, list(all_course_data_dict.values()))
    print("\nScan complete.")
    print(f"  - Added {new_courses_found_count} new courses.")
    print(f"  - Updated/Re-confirmed {updated_courses_count} existing courses.")
    print(f"  - Total courses in '{JSON_OUTPUT_FILE}': {len(all_course_data_dict)}")


if __name__ == "__main__":
    print("Starting MFRI FIRE-101 detailed course scan and data extraction...")

    # --- Customizable Scan Range ---
    # SXXX range (e.g., S000 to S999 is range(0, 1000))
    scan_s_start = 0
    scan_s_end = 1000  # FOR TESTING. Set to 1000 for full S000-S999 scan.

    # Specific years to scan
    # Use datetime.year for previous year, current year and next year
    scan_years = [
        datetime.now().year - 1,  # Previous year
        datetime.now().year,  # Current year
        datetime.now().year + 1,  # Next year
    ]
    # scan_years = [2023, 2024, 2025, 2026]  # Adjust as needed
    # --- End Customizable Scan Range ---

    scrape_mfri_courses(
        s_range_start=scan_s_start, s_range_end=scan_s_end, years_list=scan_years
    )

    print("\n--- Process Finished ---")
