# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "folium>=0.14.0",
# ]
# ///
# uv run generate_map.py
import json
from datetime import datetime
from folium.plugins import LocateControl  # type: ignore
import folium  # type: ignore
import os


def get_month_color(month_number):
    """
    Returns a dictionary of month numbers to hex color codes, or a single color for a given month number.
    Returns a hex color code for a given month number.
    """
    colors = {
        1: "#00008B",  # DarkBlue (January)
        2: "#0000FF",  # Blue (February)
        3: "#ADD8E6",  # LightBlue (March)
        4: "#00FFFF",  # Cyan (April)
        5: "#90EE90",  # LightGreen (May)
        6: "#FFFF00",  # Yellow (June)
        7: "#FF0000",  # Red (July)
        8: "#FF4500",  # OrangeRed (August)
        9: "#FFA500",  # Orange (September)
        10: "#FA8072",  # Salmon (October)
        11: "#87CEEB",  # SkyBlue (November)
        12: "#0000CD",  # MediumBlue (December)
    }
    if month_number is None:  # Return the whole dict if no number is given
        return colors
    else:
        return colors.get(
            month_number, "#808080"
        )  # Default to Gray if month is invalid


def create_map(
    json_file_path,
    output_html_path,
    geojson_boundary_file_path=None,
    inactive_class_locations_data=None,
):
    """
    Creates a Folium map with markers based on JSON data.

    Args:
        json_file_path (str): Path to the input JSON file.
        output_html_path (str): Path to save the generated HTML map.
        geojson_boundary_file_path (str, optional): Path to the GeoJSON boundary file. Defaults to None.
    """
    try:
        with open(json_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        return

    # Initialize map centered on Maryland
    maryland_map = folium.Map(location=[39.0, -76.8], zoom_start=8)

    # Add title to the map
    title_html = """
                 <h3 align="center" style="font-size:20px"><b>Find a Firefighter I Class near you</b></h3>
                 """
    maryland_map.get_root().html.add_child(folium.Element(title_html))

    # Alternative way to add title if the above causes issues with some folium versions or for more complex HTML:
    # figure = Figure()
    # figure.html.add_child(Element(title_html))
    # maryland_map.get_root().add_child(figure)
    # Or, for simpler text, sometimes this works directly, but might not be as robust for styling:
    # from branca.element import Element
    # maryland_map.get_root().html.add_child(Element("<h3>Find a Firefighter I Class near you</h3>"))

    # Add Maryland state border if GeoJSON file is provided
    if geojson_boundary_file_path:
        try:
            with open(geojson_boundary_file_path, "r") as f:
                maryland_geojson_data = json.load(f)

            def style_function(x):
                return {
                    "fillColor": "#ffffff00",  # Transparent fill
                    "color": "black",  # Border color
                    "weight": 2,  # Border weight
                    "fillOpacity": 0.0,  # No fill
                }

            folium.GeoJson(
                maryland_geojson_data,
                style_function=style_function,
                name="Maryland Border",
            ).add_to(maryland_map)
        except FileNotFoundError:
            print(
                f"Warning: GeoJSON boundary file not found at {geojson_boundary_file_path}. Border will not be drawn."
            )
        except json.JSONDecodeError:
            print(
                f"Error: Could not decode GeoJSON from {geojson_boundary_file_path}. Border will not be drawn."
            )
        except Exception as e:
            print(
                f"Warning: An unexpected error occurred while processing GeoJSON boundary file {geojson_boundary_file_path}: {e}. Border will not be drawn."
            )

    for item in data:
        try:
            # Parse latitude and longitude
            lat_long_str = item.get("locationLatitudeLongitude")
            if not lat_long_str or not isinstance(lat_long_str, str):
                print(
                    f"Warning: Missing or invalid 'locationLatitudeLongitude' for item: {item.get('courseId', 'Unknown CourseID')}"
                )
                continue

            # Splitting assuming format "latitude, longitude"
            parts = lat_long_str.split(",")
            if len(parts) != 2:
                print(
                    f"Warning: Could not parse latitude and longitude from '{lat_long_str}' for item: {item.get('courseId', 'Unknown CourseID')}"
                )
                continue

            latitude = float(parts[0].strip())
            longitude = float(parts[1].strip())

            # Extract location and courseId for popup
            location = item.get("location", "N/A")
            course_id = item.get("courseId", "N/A")
            display_name = item.get("locationDisplayName", "N/A")
            days = item.get("days", "N/A")
            start_date = item.get("startDate", "N/A")
            class_time = item.get("firstClassTime", "N/A")
            directions_url = item.get("locationGoogleMapsDirectionsUrl", "#")
            register_link = item.get("registerLink", "#")
            registration_closes = item.get("registrationCloses", "N/A")

            marker_color = "#808080"  # Default color (Gray)
            if start_date:
                try:
                    date_obj = datetime.strptime(
                        str(start_date), "%m-%d-%Y"
                    )  # Ensure start_date is string
                    month = date_obj.month
                    marker_color = get_month_color(month)
                except ValueError:
                    print(
                        f"Warning: Could not parse startDate '{start_date}' for item: {item.get('courseId', 'Unknown CourseID')}. Using default color."
                    )
            else:
                print(
                    f"Warning: Missing 'startDate' for item: {item.get('courseId', 'Unknown CourseID')}. Using default color."
                )

            # Create marker and add to map
            popup_html = f"""
            <b>Location:</b> {location}<br>
            <b>Display Name:</b> {display_name}<br>
            <b>Course ID:</b> {course_id}<br>
            <b>Start Date:</b> {start_date}<br>
            <b>Days:</b> {days}<br>
            <b>Registration Closes:</b> {registration_closes}<br>
            <b>Time:</b> {class_time}<br>
            <a href="{directions_url}" target="_blank">Get Directions</a><br>
            <a href="{register_link}" target="_blank">Register Here</a>
            """
            print(
                f"  Plotting ACTIVE class: '{display_name}' (Course ID: {course_id}) at [{latitude},{longitude}] with color {marker_color}"
            )
            # Make outline same color as fill
            folium.CircleMarker(
                location=[latitude, longitude],
                popup=folium.Popup(popup_html, max_width=300),
                color=marker_color,
                fill=True,
                fill_color=marker_color,
                fill_opacity=1,
                radius=7,
            ).add_to(maryland_map)

        except ValueError:
            print(
                f"Warning: Could not convert latitude/longitude to float for item: {item.get('courseId', 'Unknown CourseID')}"
            )
            continue
        except Exception as e:
            print(
                f"Warning: An unexpected error occurred while processing item {item.get('courseId', 'Unknown CourseID')}: {e}"
            )
            continue

    # Plot inactive class locations
    if inactive_class_locations_data:
        for location_name, details in inactive_class_locations_data.items():
            lat_long_str = details.get("lat_long")
            start_dates = details.get("start_dates", [])

            if not lat_long_str or not isinstance(lat_long_str, str):
                print(
                    f"Warning: Missing or invalid 'lat_long' for inactive location: {location_name}"
                )
                continue

            parts = lat_long_str.split(",")
            if len(parts) != 2:
                print(
                    f"Warning: Could not parse latitude and longitude from '{lat_long_str}' for inactive location: {location_name}"
                )
                continue

            try:
                latitude = float(parts[0].strip())
                longitude = float(parts[1].strip())
            except ValueError:
                print(
                    f"Warning: Could not parse lat/long for inactive location: {location_name}"
                )
                continue

            comma_separated_start_dates = ", ".join(
                sorted(list(set(s for s in start_dates if s)))
            )  # Sort and unique

            popup_html = f"""
            <b>Location Display Name:</b> {location_name}<br>
            <b>Inactive Course Start Dates:</b> {comma_separated_start_dates}
            """

            print(
                f"  Plotting INACTIVE location: '{location_name}' at [{latitude},{longitude}] with past start dates: {comma_separated_start_dates}"
            )
            folium.CircleMarker(
                location=[latitude, longitude],
                popup=folium.Popup(popup_html, max_width=300),
                color="#000000",
                fill=True,
                fill_color="#000000",
                fill_opacity=1,
                radius=6,  # Slightly smaller radius
            ).add_to(maryland_map)

    # Add legend
    # Get the colors and month names
    month_colors = get_month_color(None)  # Get the full dictionary
    month_names = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }
    # Sort the months by number for consistent legend order (1-12, then 0)
    sorted_months = sorted(month_colors.keys())

    legend_header_height_px = 38  # Approximate height of the header in pixels
    legend_header_height_css = f"{legend_header_height_px}px"

    legend_items_html = """
    <div style="display: flex; align-items: center; margin-bottom: 3px;">
        <i style="background:#000000; width: 15px; height: 15px; display: inline-block; margin-right: 5px; border: 1px solid #555;"></i>
        <span>Inactive Classes</span>
    </div>
    """
    for month_num in sorted_months:
        color = month_colors[month_num]
        name = month_names[month_num]
        legend_items_html += f"""
        <div style="display: flex; align-items: center; margin-bottom: 3px;">
            <i style="background:{color}; width: 15px; height: 15px; display: inline-block; margin-right: 5px; border: 1px solid #888;"></i>
            <span>{name}</span>
        </div>
        """

    legend_html = f"""
    <style>
        #mapLegend {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            width: 130px; /* Initial width for minimized state */
            border: 2px solid grey;
            z-index: 9999;
            font-size: 14px;
            background-color: white;
            opacity: 0.95; /* Slightly increased opacity */
            transition: max-height 0.3s ease-in-out, width 0.3s ease-in-out;
            max-height: {legend_header_height_css}; /* Initial height for minimized state (header only) */
            overflow: hidden; /* Crucial for collapse animation */
            border-radius: 5px; /* Optional: rounded corners */
            box-shadow: 0 2px 5px rgba(0,0,0,0.2); /* Optional: subtle shadow */
        }}
        #legendHeader {{
            cursor: pointer;
            padding: 8px;
            background-color: #f0f0f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            /* border-bottom is managed by JS */
        }}
        #legendHeader span {{ /* Style for text within header */
            font-weight: bold;
        }}
        #legendToggleIcon {{ /* Style for the [+] / [-] icon */
            margin-left: 10px; /* Space between title and icon */
        }}
        #legendContent {{
            padding: 8px; /* Padding for the items area */
            max-height: 200px; /* Max height for the scrollable content area */
            overflow-y: auto; /* Add scroll if content exceeds max-height */
            display: none; /* Start minimized */
        }}
    </style>
    <div id="mapLegend">
      <div id="legendHeader" onclick="toggleLegend()">
          <span>Legend</span>
          <span id="legendToggleIcon">[+]</span>
      </div>
      <div id="legendContent">
        {legend_items_html}
      </div>
    </div>

    <script type="text/javascript">
        function toggleLegend() {{
            var legend = document.getElementById('mapLegend');
            var content = document.getElementById('legendContent');
            var icon = document.getElementById('legendToggleIcon');
            var header = document.getElementById('legendHeader');

            if (content.style.display === 'none') {{ // If it's minimized, expand it
                content.style.display = 'block';
                icon.textContent = '[-]';
                legend.style.maxHeight = '250px'; // Max height for expanded legend (header + content)
                legend.style.width = '180px';     // Expanded width
                header.style.borderBottom = '1px solid #ccc'; // Add border to header when expanded
            }} else {{ // If it's expanded, minimize it
                content.style.display = 'none';
                icon.textContent = '[+]';
                legend.style.maxHeight = '{legend_header_height_css}'; // Height of header only
                legend.style.width = '130px';      // Minimized width
                header.style.borderBottom = 'none'; // Remove border from header when minimized
            }}
        }}
    </script>
    """
    maryland_map.get_root().html.add_child(folium.Element(legend_html))

    # Get current timestamp for "Last updated"
    last_updated_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Add footer text
    footer_html = f"""
                 <div style="text-align: center; margin-top: 10px; font-size: 12px; color: #333; line-height: 1.6;">
                     Last updated: {last_updated_timestamp}
                     | Vibe coded with AI. May contain errors.
                     | Color is based on month when the class starts. See Legend for more information.
                     | Black color shows inactive classes that have no current classes at this location but may do in the future.
                     | Data taken from <a href="https://www.mfri.org/course/msfs/FIRE/101/" target="_blank" style="color: #007bff; text-decoration: none;">MFRI Firefighter I Courses</a>
                     | Source code available on <a href="https://github.com/raybellwaves/find_a_firefighter_I_class_near_you" target="_blank" style="color: #007bff; text-decoration: none;">GitHub</a>
                 </div>
                 """
    maryland_map.get_root().html.add_child(folium.Element(footer_html))

    # Add LocateControl button for "zoom to current location"
    LocateControl().add_to(maryland_map)

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_html_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        except OSError as e:
            print(f"Error: Could not create directory {output_dir}. {e}")
            return

    # Save map to HTML file
    try:
        maryland_map.save(output_html_path)
    except Exception as e:
        print(f"Error: Could not save map to {output_html_path}. {e}")
        return


if __name__ == "__main__":
    all_courses_file = "mfri_firefigher_I_old_and_new_courses.json"
    current_classes_file = "current_firefighter_I_classes.json"
    output_html = "docs/index.html"
    geojson_boundary_file = "maryland-single.geojson"  # Place your GeoJSON file here

    all_courses_data = []
    try:
        with open(all_courses_file, "r") as f:
            all_courses_data = json.load(f)
        print(f"Loaded {len(all_courses_data)} records from {all_courses_file}")
    except FileNotFoundError:
        print(
            f"Error: File not found {all_courses_file}. Starting with empty data for all courses."
        )
    except json.JSONDecodeError:
        print(
            f"Error: Could not decode JSON from {all_courses_file}. Starting with empty data for all courses."
        )

    current_classes_data = []
    try:
        with open(current_classes_file, "r") as f:
            current_classes_data = json.load(f)
        print(f"Loaded {len(current_classes_data)} records from {current_classes_file}")
    except FileNotFoundError:
        print(
            f"Error: File not found {current_classes_file}. Cannot proceed without current classes."
        )
        exit()  # Or handle appropriately
    except json.JSONDecodeError:
        print(
            f"Error: Could not decode JSON from {current_classes_file}. Cannot proceed."
        )
        exit()  # Or handle appropriately

    # Note: The create_map function currently takes a file path.
    # This will need to be updated in a subsequent step to accept the loaded data directly.
    # For now, we'll pass the current_classes_file path as before to keep the script runnable,
    # though the data from current_classes_data is what we'd ideally use.

    # Get a set of locationDisplayNames that have active classes
    active_location_display_names = {
        course.get("locationDisplayName")
        for course in current_classes_data
        if course.get("locationDisplayName")
    }
    print(
        f"Found {len(active_location_display_names)} unique active location display names."
    )

    # Identify inactive courses (courses not in current_classes_data by courseId)
    current_course_ids = {
        course.get("courseId")
        for course in current_classes_data
        if course.get("courseId")
    }
    inactive_courses_data = []
    for course in all_courses_data:
        if course.get("courseId") not in current_course_ids:
            inactive_courses_data.append(course)

    print(
        f"Found {len(inactive_courses_data)} courses in total that are not currently active (by courseId)."
    )

    # Process inactive courses to group by location,
    # but only for locations that DO NOT have an active class.
    processed_inactive_classes = {}
    for course in inactive_courses_data:
        location_display_name = course.get("locationDisplayName")
        start_date = course.get("startDate")
        lat_long = course.get("locationLatitudeLongitude")

        if not location_display_name:  # Skip if essential data is missing
            continue

        # If this location already has an active class, skip adding it as an inactive-only location.
        if location_display_name in active_location_display_names:
            # print(f"    Skipping '{location_display_name}' for inactive plotting because it has active classes.")
            continue

        if location_display_name not in processed_inactive_classes:
            processed_inactive_classes[location_display_name] = {
                "lat_long": lat_long,
                "start_dates": [start_date] if start_date else [],
            }
            # print(
            #     f"    Adding '{location_display_name}' to inactive plot list. Lat/Long: {lat_long}, Initial Start Date: {start_date}"
            # )
        else:
            if (
                start_date
                and start_date
                not in processed_inactive_classes[location_display_name]["start_dates"]
            ):
                processed_inactive_classes[location_display_name]["start_dates"].append(
                    start_date
                )
                # print(
                #     f"    Appending start date '{start_date}' to existing inactive location '{location_display_name}'."
                # )

    print(
        f"Processed {len(processed_inactive_classes)} unique locations that will be marked as having only past/inactive classes."
    )
    # Sort the dates in descending order (most recent first)
    for location, details in processed_inactive_classes.items():
        # Check if 'start_dates' key exists and the list is not empty
        if "start_dates" in details and details["start_dates"]:
            try:
                # Sorts the list of strings in-place.
                # The key converts string to datetime object for correct chronological comparison.
                # reverse=True sorts from newest to oldest.
                details["start_dates"].sort(
                    key=lambda date_str: datetime.strptime(date_str, "%m-%d-%Y"),
                    reverse=True,
                )
            except ValueError as e:
                # This will catch errors if a date string doesn't match "%m-%d-%Y"
                print(
                    f"Error parsing dates for {location}: {e}. Dates: {details['start_dates']}"
                )
                # You might want to decide how to handle this: skip, log, leave unsorted, etc.
                # For now, it will print the error and leave that specific list as it was if an error occurs mid-sort.
                pass
            except TypeError as e:
                # This might catch errors if details["start_dates"] is not a list or contains non-string items
                print(
                    f"TypeError for {location}: {e}. 'start_dates' might not be a list of strings. Value: {details['start_dates']}"
                )
                pass

    create_map(
        current_classes_file,
        output_html,
        geojson_boundary_file,
        inactive_class_locations_data=processed_inactive_classes,
    )

    # Check if the file was created before printing success,
    # as create_map has its own error handling and might return early.
    if os.path.exists(output_html):
        print(f"Map generated successfully at {output_html}")
