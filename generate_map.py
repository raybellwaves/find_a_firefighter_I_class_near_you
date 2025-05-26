# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "folium>=0.14.0",
# ]
# ///
# uv run generate_map.py
import json
from datetime import datetime  # Added import
import folium
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
            <b>Time:</b> {class_time}<br>
            <a href="{directions_url}" target="_blank">Get Directions</a><br>
            <a href="{register_link}" target="_blank">Register Here</a>
            """
            folium.CircleMarker(
                location=[latitude, longitude],
                popup=folium.Popup(popup_html, max_width=300),
                color=marker_color,
                fill=True,
                fill_color=marker_color,
                fill_opacity=0.7,
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
    # Add the default gray color for "Unknown/No Date"
    month_colors[0] = "#808080"
    month_names[0] = "Unknown/No Date"

    # Sort the months by number for consistent legend order (1-12, then 0)
    sorted_months = sorted(month_colors.keys())

    legend_html = """
    <div style="position: fixed;
                bottom: 20px; left: 50%; transform: translateX(-50%); width: 180px; max-height: 250px; overflow-y: auto;
                border: 2px solid grey; z-index: 9999; font-size: 14px;
                background-color: white; opacity: 0.9; padding: 10px;">
      <div style="font-weight: bold; text-align: center; margin-bottom: 5px;">Start Month Color Key</div>
      <div style="height: 1px; background-color: grey; margin: 5px 0;"></div> <!-- Separator -->
    """

    for month_num in sorted_months:
        color = month_colors[month_num]
        name = month_names[month_num]
        legend_html += f"""
        <div style="display: flex; align-items: center; margin-bottom: 3px;">
            <i style="background:{color}; width: 15px; height: 15px; display: inline-block; margin-right: 5px; border: 1px solid #888;"></i>
            <span>{name}</span>
        </div>
        """

    legend_html += """
    </div>
    """
    maryland_map.get_root().html.add_child(folium.Element(legend_html))

    # Add footer text
    footer_html = """
                 <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #333;">
                     Data taken from <a href="https://www.mfri.org/course/msfs/FIRE/101/" target="_blank" style="color: #007bff; text-decoration: none;">https://www.mfri.org/course/msfs/FIRE/101/</a>
                 </div>
                 """
    maryland_map.get_root().html.add_child(folium.Element(footer_html))

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
    json_file = "current_firefighter_I_classes.json"
    output_html = "docs/index.html"
    geojson_boundary_file = "maryland-single.geojson"  # Place your GeoJSON file here

    create_map(json_file, output_html, geojson_boundary_file)
    # Check if the file was created before printing success,
    # as create_map has its own error handling and might return early.
    if os.path.exists(output_html):
        print(f"Map generated successfully at {output_html}")
