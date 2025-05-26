import json
import folium
import os
from datetime import datetime

def get_month_color(month_number):
    """
    Returns a hex color code for a given month number.
    """
    colors = {
        1: '#00008B',  # DarkBlue (January)
        2: '#0000FF',  # Blue (February)
        3: '#ADD8E6',  # LightBlue (March)
        4: '#00FFFF',  # Cyan (April)
        5: '#90EE90',  # LightGreen (May)
        6: '#FFFF00',  # Yellow (June)
        7: '#FF0000',  # Red (July)
        8: '#FF4500',  # OrangeRed (August)
        9: '#FFA500',  # Orange (September)
        10: '#FA8072', # Salmon (October)
        11: '#87CEEB', # SkyBlue (November)
        12: '#0000CD'  # MediumBlue (December)
    }
    return colors.get(month_number, '#808080') # Default to Gray if month is invalid

def create_map(json_file_path, output_html_path):
    """
    Creates a Folium map with markers based on JSON data.

    Args:
        json_file_path (str): Path to the input JSON file.
        output_html_path (str): Path to save the generated HTML map.
    """
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        return

    # Initialize map centered on Maryland.
    m = folium.Map(location=[39.0, -76.8], zoom_start=8)

    for item in data:
        try:
            lat_long_str = item.get('locationLatitudeLongitude')
            if not lat_long_str or not isinstance(lat_long_str, str):
                print(f"Warning: Missing or invalid 'locationLatitudeLongitude' for item: {item.get('courseId', 'Unknown CourseID')}")
                continue

            parts = lat_long_str.split(',')
            if len(parts) != 2:
                print(f"Warning: Could not parse latitude and longitude from '{lat_long_str}' for item: {item.get('courseId', 'Unknown CourseID')}")
                continue
            
            latitude = float(parts[0].strip())
            longitude = float(parts[1].strip())

            location = item.get('location', 'N/A')
            course_id = item.get('courseId', 'N/A')
            start_date_str = item.get('startDate')

            marker_color = '#808080' # Default color (Gray)
            if start_date_str:
                try:
                    date_obj = datetime.strptime(start_date_str, "%m-%d-%Y")
                    month = date_obj.month
                    marker_color = get_month_color(month)
                except ValueError:
                    print(f"Warning: Could not parse startDate '{start_date_str}' for item: {item.get('courseId', 'Unknown CourseID')}. Using default color.")
            else:
                print(f"Warning: Missing 'startDate' for item: {item.get('courseId', 'Unknown CourseID')}. Using default color.")

            popup_text = f"{location}<br>Course ID: {course_id}<br>Start Date: {start_date_str if start_date_str else 'N/A'}"
            
            folium.CircleMarker(
                location=[latitude, longitude],
                radius=7,
                popup=popup_text,
                color=marker_color,
                fill=True,
                fill_color=marker_color,
                fill_opacity=0.7
            ).add_to(m)

        except ValueError: # Catches float conversion errors for lat/lon
            print(f"Warning: Could not convert latitude/longitude to float for item: {item.get('courseId', 'Unknown CourseID')}")
            continue
        except Exception as e:
            print(f"Warning: An unexpected error occurred while processing item {item.get('courseId', 'Unknown CourseID')}: {e}")
            continue
            
    output_dir = os.path.dirname(output_html_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        except OSError as e:
            print(f"Error: Could not create directory {output_dir}. {e}")
            return

    try:
        m.save(output_html_path)
    except Exception as e:
        print(f"Error: Could not save map to {output_html_path}. {e}")
        return

if __name__ == "__main__":
    json_file = 'current_firefighter_I_classes.json'
    output_html = 'docs/firefighter_classes_map.html'
    
    create_map(json_file, output_html)
    if os.path.exists(output_html):
        print(f"Map generated successfully at {output_html}")
