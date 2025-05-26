import json
import folium
import os

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

    # Initialize map centered on Maryland
    maryland_map = folium.Map(location=[39.0, -76.8], zoom_start=8)

    for item in data:
        try:
            # Parse latitude and longitude
            lat_long_str = item.get('locationLatitudeLongitude')
            if not lat_long_str or not isinstance(lat_long_str, str):
                print(f"Warning: Missing or invalid 'locationLatitudeLongitude' for item: {item.get('courseId', 'Unknown CourseID')}")
                continue

            # Splitting assuming format "latitude, longitude"
            parts = lat_long_str.split(',')
            if len(parts) != 2:
                print(f"Warning: Could not parse latitude and longitude from '{lat_long_str}' for item: {item.get('courseId', 'Unknown CourseID')}")
                continue
            
            latitude = float(parts[0].strip())
            longitude = float(parts[1].strip())

            # Extract location and courseId for popup
            location = item.get('location', 'N/A')
            course_id = item.get('courseId', 'N/A')

            # Create marker and add to map
            popup_text = f"{location}<br>Course ID: {course_id}"
            folium.Marker(
                location=[latitude, longitude],
                popup=popup_text
            ).add_to(maryland_map)

        except ValueError:
            print(f"Warning: Could not convert latitude/longitude to float for item: {item.get('courseId', 'Unknown CourseID')}")
            continue
        except Exception as e:
            print(f"Warning: An unexpected error occurred while processing item {item.get('courseId', 'Unknown CourseID')}: {e}")
            continue
            
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
    json_file = 'current_firefighter_I_classes.json'
    output_html = 'docs/firefighter_classes_map.html'
    
    create_map(json_file, output_html)
    # Check if the file was created before printing success, 
    # as create_map has its own error handling and might return early.
    if os.path.exists(output_html):
        print(f"Map generated successfully at {output_html}")
