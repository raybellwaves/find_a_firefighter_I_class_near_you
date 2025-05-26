# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "beautifulsoup4>=4.12.0",
#     "requests>=2.31.0",
# ]
# ///
# uv run classes.py
import requests  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
import json
from datetime import datetime
import re
import os


def extract_text_after_colon(tag, label):
    """Helper function to extract text after a specific label like 'Start Date: '"""
    if tag:
        found_label = False
        for s in tag.stripped_strings:
            if label in s:
                found_label = True
            elif found_label and s:
                return s.strip()
        nobr_tag = tag.find(string=re.compile(label))
        if nobr_tag and nobr_tag.find_next_sibling("nobr"):
            return nobr_tag.find_next_sibling("nobr").string.strip()
    return None


def extract_courses(html_doc, locations_lookup):
    soup = BeautifulSoup(html_doc, "html.parser")
    courses_data = []
    current_date_str = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )  # Changed format for more detail

    event_items = soup.find_all("div", class_="row event-item")

    if not event_items:
        print(
            "No event items found with class 'row event-item'. Check the HTML structure."
        )
        return []

    for item_index, item in enumerate(event_items):
        # Initialize course_info with all potential fields
        course_info = {
            "courseId": None,
            "registerLink": None,
            "classUrl": None,  # New field for the "More ->" link
            "startDate": None,
            "endDate": None,
            "firstClassTime": None,
            "days": None,
            "registrationOpens": None,
            "registrationCloses": None,
            "location": None,  # This is the join key
            "coordinateBy": None,
            "contact": None,
            "locationUrlId": None,
            "locationRegionId": None,  # e.g., Prince George's
            "locationServedBy": None,
            "locationServedByUrl": None,
            "locationWebsiteAddress": None,
            "locationFormattedAddress": None,
            "locationLatitudeLongitude": None,
            "locationDisplayName": None,  # Google's name for the place
            "locationGoogleMapsUrl": None,
            "locationGoogleMapsDirectionsUrl": None,
            "currentDate": current_date_str,
        }

        # courseId and registerLink
        course_id_tag = item.find("div", class_="col-md-2")
        if course_id_tag and course_id_tag.find("h5"):
            h5_for_id_link = course_id_tag.find("h5")
            if h5_for_id_link:
                if h5_for_id_link.contents:
                    course_info["courseId"] = h5_for_id_link.contents[0].strip()
                else:
                    course_info["courseId"] = None
                register_a_tag = h5_for_id_link.find("a")
                if register_a_tag and register_a_tag.get("href"):
                    # Make registerLink absolute
                    relative_register_url = register_a_tag.get("href")
                    course_info["registerLink"] = requests.compat.urljoin(
                        url, relative_register_url
                    )
                else:
                    course_info["registerLink"] = None
            else:
                course_info["courseId"] = None
                course_info["registerLink"] = None
        else:
            course_info["courseId"] = None
            course_info["registerLink"] = None

        # Class URL
        course_info["classUrl"] = (
            "https://www.mfri.org/course/msfs/FIRE/101/"
            + course_info["courseId"].split("-")[-2]
            + "/"
            + course_info["courseId"].split("-")[-1]
            if course_info["courseId"]
            else None
        )

        # Dates, Time, Days
        date_time_days_div = item.find("div", class_="col-md-3")
        if date_time_days_div:
            h5_tag = date_time_days_div.find("h5", class_="mt-2 body-color")
            if h5_tag:
                nobr_tags = h5_tag.find_all("nobr")
                if len(nobr_tags) >= 2:
                    course_info["startDate"] = (
                        nobr_tags[0].string.strip() if nobr_tags[0].string else None
                    )
                    course_info["endDate"] = (
                        nobr_tags[1].string.strip() if nobr_tags[1].string else None
                    )
                else:
                    course_info["startDate"] = None
                    course_info["endDate"] = None

                if len(nobr_tags) >= 4:
                    time_parts = [
                        (nobr_tags[2].string.strip() if nobr_tags[2].string else ""),
                        (nobr_tags[3].string.strip() if nobr_tags[3].string else ""),
                    ]
                    course_info["firstClassTime"] = (
                        f"{time_parts[0]} - {time_parts[1]}"
                        if any(time_parts)
                        else None
                    )
                    if course_info["firstClassTime"] == " - ":
                        course_info["firstClassTime"] = None

                else:  # Fallback for time if nobr structure differs
                    time_text_node = h5_tag.find(
                        string=re.compile(r"First Class Time:")
                    )
                    if time_text_node:
                        time_nobrs_alt = time_text_node.find_next_siblings(
                            "nobr", limit=2
                        )
                        if len(time_nobrs_alt) == 2:
                            time_p = [
                                (
                                    time_nobrs_alt[0].string.strip()
                                    if time_nobrs_alt[0].string
                                    else ""
                                ),
                                (
                                    time_nobrs_alt[1].string.strip()
                                    if time_nobrs_alt[1].string
                                    else ""
                                ),
                            ]
                            course_info["firstClassTime"] = (
                                f"{time_p[0]} - {time_p[1]}" if any(time_p) else None
                            )
                            if course_info["firstClassTime"] == " - ":
                                course_info["firstClassTime"] = None
                        else:
                            course_info["firstClassTime"] = None
                    else:
                        course_info["firstClassTime"] = None

                days_span = h5_tag.find(
                    "span", class_="mt-2 body-color"
                )  # Original attempt
                if days_span and days_span.string:
                    course_info["days"] = days_span.string.strip()
                else:  # Fallback for days
                    # Iterate through contents to find the day string, typically after <br> tags
                    # and not part of date/time lines
                    possible_day_strings = []
                    for content_part in h5_tag.contents:
                        if isinstance(content_part, str):
                            stripped_part = content_part.strip()
                            if (
                                stripped_part
                                and any(
                                    day.lower() in stripped_part.lower()
                                    for day in [
                                        "Monday",
                                        "Tuesday",
                                        "Wednesday",
                                        "Thursday",
                                        "Friday",
                                        "Saturday",
                                        "Sunday",
                                    ]
                                )
                                and "First Class Time:" not in stripped_part
                            ):
                                possible_day_strings.append(stripped_part)
                        elif (
                            content_part.name == "span" and content_part.string
                        ):  # Check spans without specific class too
                            stripped_span_text = content_part.string.strip()
                            if any(
                                day.lower() in stripped_span_text.lower()
                                for day in [
                                    "Monday",
                                    "Tuesday",
                                    "Wednesday",
                                    "Thursday",
                                    "Friday",
                                    "Saturday",
                                    "Sunday",
                                ]
                            ):
                                possible_day_strings.append(stripped_span_text)
                    if possible_day_strings:
                        course_info["days"] = possible_day_strings[
                            -1
                        ]  # Usually the last one is correct
                    else:
                        course_info["days"] = None
            else:  # h5_tag for date/time not found
                course_info["startDate"] = None
                course_info["endDate"] = None
                course_info["firstClassTime"] = None
                course_info["days"] = None
        else:  # date_time_days_div not found
            course_info["startDate"] = None
            course_info["endDate"] = None
            course_info["firstClassTime"] = None
            course_info["days"] = None

        # Registration Dates
        all_col_md_3_divs = item.find_all("div", class_="col-md-3", recursive=False)
        registration_div = None
        if len(all_col_md_3_divs) > 1:
            for div_candidate in all_col_md_3_divs:
                if div_candidate != date_time_days_div and div_candidate.find(
                    string=re.compile("Registration Open:")
                ):  # Ensure it's not the date/time div
                    registration_div = div_candidate
                    break
            if (
                not registration_div
                and date_time_days_div
                and all_col_md_3_divs[0] == date_time_days_div
                and len(all_col_md_3_divs) > 1
            ):
                registration_div = all_col_md_3_divs[
                    1
                ]  # Assume second if first was date/time

        if registration_div:
            h5_reg_tag = registration_div.find("h5", class_="mt-2 body-color")
            if h5_reg_tag:
                nobr_tags_reg = h5_reg_tag.find_all("nobr")
                if len(nobr_tags_reg) >= 2:
                    course_info["registrationOpens"] = (
                        nobr_tags_reg[0].string.strip()
                        if nobr_tags_reg[0].string
                        else None
                    )
                    course_info["registrationCloses"] = (
                        nobr_tags_reg[1].string.strip()
                        if nobr_tags_reg[1].string
                        else None
                    )
                else:
                    course_info["registrationOpens"] = None
                    course_info["registrationCloses"] = None
            else:
                course_info["registrationOpens"] = None
                course_info["registrationCloses"] = None
        else:
            course_info["registrationOpens"] = None
            course_info["registrationCloses"] = None

        # Location
        location_div = item.find("div", class_="col-md-4")
        if location_div and location_div.find("h5"):
            h5_loc_tag = location_div.find("h5")
            location_text = ""
            for content in h5_loc_tag.contents:
                if isinstance(content, str):
                    cleaned_content = content.replace("\xa0", " ").strip()
                    if cleaned_content:
                        location_text = cleaned_content
                        break
            course_info["location"] = location_text if location_text else None
        else:
            course_info["location"] = None

        # --- Add data from mfri_locations.json ---
        course_location_name = course_info.get("location")
        best_match_loc_data = None
        longest_match_len = 0

        if course_location_name:
            # Iterate through the canonical location names from mfri_locations.json
            for mfri_loc_name_key, mfri_loc_data_value in locations_lookup.items():
                # Check if the canonical name is a substring of the scraped course location
                if mfri_loc_name_key in course_location_name:
                    if len(mfri_loc_name_key) > longest_match_len:
                        longest_match_len = len(mfri_loc_name_key)
                        best_match_loc_data = mfri_loc_data_value

        if best_match_loc_data:
            course_info["locationUrlId"] = best_match_loc_data.get("urlId")
            course_info["locationRegionId"] = best_match_loc_data.get("id")
            course_info["locationServedBy"] = best_match_loc_data.get("servedBy")
            course_info["locationServedByUrl"] = best_match_loc_data.get("servedByUrl")
            course_info["locationWebsiteAddress"] = best_match_loc_data.get(
                "websiteAddress"
            )
            course_info["locationFormattedAddress"] = best_match_loc_data.get(
                "formattedAddress"
            )
            course_info["locationLatitudeLongitude"] = best_match_loc_data.get(
                "locationLatitudeLongitude"
            )
            course_info["locationDisplayName"] = best_match_loc_data.get("displayName")
            course_info["locationGoogleMapsUrl"] = best_match_loc_data.get(
                "googleMapsUrl"
            )
            course_info["locationGoogleMapsDirectionsUrl"] = best_match_loc_data.get(
                "googleMapsDirectionsUrl"
            )
        elif (
            course_location_name and course_location_name != "N/A"
        ):  # Avoid printing for courses with no location
            print(
                f"    -> Note: Location '{course_location_name}' for course '{course_info.get('courseId', 'N/A')}' not found in mfri_locations.json with substring match."
            )

        # Coordinated By and Contact (Revised Logic)
        course_info["coordinateBy"] = None
        course_info["contact"] = None

        h5_coord_tag = None
        # Find the specific col-md-11 that contains the coordination info
        all_col_md_11_for_coord = item.find_all("div", class_="col-md-11")
        for div_element in all_col_md_11_for_coord:
            h5_candidate = div_element.find("h5", class_="mt-2 body-color")
            if h5_candidate and "Coordinated by:" in h5_candidate.get_text(strip=True):
                h5_coord_tag = h5_candidate
                break

        if h5_coord_tag:
            full_text = h5_coord_tag.get_text(separator=" ", strip=True)

            # Extract Coordinator
            # Captures text after "Coordinated by:" up to a period before "For questions contact:",
            # or up to "For questions contact:" if no period, or to the end of the string.
            coord_pattern = r"Coordinated by:\s*(.*?)(?:\s*\.\s*For questions contact:|\s+For questions contact:|$)"
            coord_match = re.search(coord_pattern, full_text, re.IGNORECASE)
            if coord_match:
                course_info["coordinateBy"] = coord_match.group(1).strip()

            # Extract Contact
            contact_pattern = r"For questions contact:\s*(.*)"
            contact_match = re.search(contact_pattern, full_text, re.IGNORECASE)
            if contact_match:
                contact_text_from_regex = contact_match.group(1).strip()
                course_info["contact"] = (
                    contact_text_from_regex  # Default to text from regex
                )

                # Refine contact from mailto: link if present within this h5_coord_tag
                for a_tag in h5_coord_tag.find_all(
                    "a"
                ):  # Check all <a> tags in this h5
                    a_href = a_tag.get("href")
                    a_text_content = a_tag.get_text(strip=True)
                    if a_href and a_href.startswith("mailto:"):
                        email_in_href = a_href[7:]
                        # If the regex-extracted text matches the link's text content OR the email in mailto href itself
                        if (
                            contact_text_from_regex.lower() == a_text_content.lower()
                            or contact_text_from_regex.lower() == email_in_href.lower()
                        ):
                            course_info["contact"] = (
                                email_in_href  # Prefer the cleaned email
                            )
                            break
                        # If the regex text is an email and matches the mailto email (even if link text is different)
                        elif (
                            "@" in contact_text_from_regex
                            and contact_text_from_regex.lower() == email_in_href.lower()
                        ):
                            course_info["contact"] = email_in_href
                            break
        # End of Coordinated By and Contact logic

        # currentDate is already set during initialization
        courses_data.append(course_info)

    return courses_data


# --- Main execution ---
url = "https://www.mfri.org/course/msfs/FIRE/101/"
output_filename = "current_firefighter_I_classes.json"
locations_json_path = "mfri_locations.json"  # Path to your locations file
html_content = None
locations_lookup = {}

# Load mfri_locations.json to create a lookup table
if os.path.exists(locations_json_path):
    try:
        with open(locations_json_path, "r") as f_loc:
            mfri_locations_list = json.load(f_loc)
        # Create a lookup dictionary by location name.
        # If multiple entries have the same location name, this will use the first one encountered.
        for loc_data in mfri_locations_list:
            loc_name = loc_data.get("location")
            if loc_name and loc_name not in locations_lookup:
                locations_lookup[loc_name] = loc_data
        print(
            f"Successfully loaded {len(locations_lookup)} unique locations from {locations_json_path} for lookup."
        )
    except Exception as e:
        print(f"Error loading or processing {locations_json_path}: {e}")
else:
    print(
        f"Warning: {locations_json_path} not found. Location details will not be added to courses."
    )

print(f"Fetching HTML content from: {url}")
try:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, timeout=15, headers=headers)
    response.raise_for_status()
    html_content = response.text
    print("Successfully fetched HTML content.")
except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occurred: {http_err} for URL: {url}")
except requests.exceptions.ConnectionError as conn_err:
    print(f"Connection error occurred: {conn_err} for URL: {url}")
except requests.exceptions.Timeout as timeout_err:
    print(f"Timeout error occurred: {timeout_err} for URL: {url}")
except requests.exceptions.RequestException as req_err:
    print(f"An error occurred during the request: {req_err} for URL: {url}")

if html_content:
    extracted_data = extract_courses(html_content, locations_lookup)

    if extracted_data:
        with open(output_filename, "w") as f:
            json.dump(extracted_data, f, indent=4)
        print(
            f"\nSuccessfully extracted {len(extracted_data)} courses to {output_filename}"
        )

        print("\nFirst extracted item:")
        print(json.dumps(extracted_data[0], indent=4))
        if len(extracted_data) > 1:
            print("\nLast extracted item:")
            print(json.dumps(extracted_data[-1], indent=4))
    else:
        print(
            "No data was extracted. The JSON file will not be created or will be empty."
        )
else:
    print("Could not retrieve HTML content, so no data was processed.")
