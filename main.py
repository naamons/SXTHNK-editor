import streamlit as st
import json
from io import BytesIO
import pandas as pd
import struct

st.set_page_config(page_title="Binary File Editor", layout="wide")

st.title("Binary File Editor")

st.markdown("""
Upload a JSON configuration file and a binary file. 
Edit the parameters as needed and save the changes back to the binary file.
""")

# File Uploaders
uploaded_json = st.file_uploader("Upload JSON File", type=["json"])
uploaded_binary = st.file_uploader("Upload Binary File", type=["bin", "dat", "exe"])

if uploaded_json and uploaded_binary:
    try:
        json_data = json.load(uploaded_json)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON file: {e}")
        st.stop()
    
    binary_data = bytearray(uploaded_binary.read())
    binary_size = len(binary_data)
    st.success(f"Binary file loaded successfully. Size: {binary_size} bytes.")
    
    # Initialize session state for edited data
    if 'edited_values' not in st.session_state:
        st.session_state.edited_values = {}
    
    # Function to apply scaling
    def apply_scaling(value, factor, offset):
        return (value * factor) + offset
    
    # Function to reverse scaling
    def reverse_scaling(value, factor, offset):
        return (value - offset) / factor
    
    # Function to determine cell data type based on cell length
    def get_cell_data_type(cell_length):
        if cell_length == 1:
            return "int8"
        elif cell_length == 2:
            return "int16"
        elif cell_length == 4:
            return "int32"
        else:
            return None  # Unsupported
    
    # Function to write a value to binary data
    def write_to_binary(offset_hex, length, data_type, sign_type, value, scaling):
        try:
            offset = int(offset_hex, 16)
        except ValueError:
            st.error(f"Invalid offset format: {offset_hex}")
            return
        if offset + length > binary_size:
            st.error(f"Offset {offset_hex} with length {length} exceeds binary file size.")
            return
        # Reverse scaling if necessary and not an array
        if scaling and data_type != "array":
            value = reverse_scaling(value, scaling.get('factor',1), scaling.get('offset',0))
        # Pack the value based on data type
        if data_type == "int8":
            fmt = 'b' if sign_type == 'signed' else 'B'
        elif data_type == "int16":
            fmt = '<h' if sign_type == 'signed' else '<H'
        elif data_type == "int32":
            fmt = '<i' if sign_type == 'signed' else '<I'
        elif data_type == "float":
            fmt = '<f'
        else:
            st.error(f"Unsupported data type: {data_type}")
            return
        try:
            packed_data = struct.pack(fmt, value)
            binary_data[offset:offset+len(packed_data)] = packed_data
        except struct.error as e:
            st.error(f"Error packing data: {e}")
    
    # Function to read a value from binary data
    def read_from_binary(offset_hex, length, data_type, sign_type, scaling):
        try:
            offset = int(offset_hex, 16)
        except ValueError:
            st.error(f"Invalid offset format: {offset_hex}")
            return None
        if offset + length > binary_size:
            st.error(f"Offset {offset_hex} with length {length} exceeds binary file size.")
            return None
        data_slice = binary_data[offset:offset+length]
        # Unpack based on data type
        if data_type == "int8":
            fmt = 'b' if sign_type == 'signed' else 'B'
        elif data_type == "int16":
            fmt = '<h' if sign_type == 'signed' else '<H'
        elif data_type == "int32":
            fmt = '<i' if sign_type == 'signed' else '<I'
        elif data_type == "float":
            fmt = '<f'
        else:
            st.error(f"Unsupported data type: {data_type}")
            return None
        try:
            value = struct.unpack(fmt, data_slice)[0]
            # Apply scaling if necessary and not an array
            if scaling and data_type != "array":
                value = apply_scaling(value, scaling.get('factor',1), scaling.get('offset',0))
            return value
        except struct.error as e:
            st.error(f"Error unpacking data: {e}")
            return None
    
    # Iterate through map_groups and editable_maps
    def process_maps(group_or_editable, group_name=""):
        if group_name:
            st.header(group_name)
        for item in group_or_editable:
            name = item.get("name")
            description = item.get("description", "")
            input_type = item.get("input_type")
            data_type = item.get("data_type")
            sign_type = item.get("sign_type", "unsigned")
            scaling = item.get("scaling", {})
            offset = item.get("offset")
            length = item.get("length")
            min_val = item.get("min_value")
            max_val = item.get("max_value")
            step = item.get("step", 1)
            default = item.get("default_value")
            map_dimension = item.get("map_dimension", {})
            editable_columns = map_dimension.get("editable_columns", [])
            editable_region = map_dimension.get("editable_region", {})
            rows = map_dimension.get("rows", 0)
            columns = map_dimension.get("columns", 0)
            
            st.subheader(name)
            st.write(description)
            
            # Initialize edited_values if not present
            if name not in st.session_state.edited_values:
                st.session_state.edited_values[name] = {}
            
            if input_type == "slider":
                # Validate slider parameters
                if min_val is None or max_val is None or step is None:
                    st.error(f"Slider '{name}' is missing 'min_value', 'max_value', or 'step'. Skipping.")
                    continue
                if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)) or not isinstance(step, (int, float)):
                    st.error(f"Slider '{name}' has invalid 'min_value', 'max_value', or 'step' types. Skipping.")
                    continue
                if min_val > max_val:
                    st.error(f"Slider '{name}' has 'min_value' greater than 'max_value'. Skipping.")
                    continue
                
                # Read current value from binary
                current_value = read_from_binary(offset, length, data_type, sign_type, scaling)
                if current_value is None:
                    current_value = default
                if current_value is None:
                    st.error(f"Slider '{name}' has no valid current or default value. Skipping.")
                    continue
                # Ensure current_value is within min and max
                current_value = max(min_val, min(max_val, current_value))
                try:
                    edited_val = st.slider(
                        label=name,
                        min_value=min_val,
                        max_value=max_val,
                        value=current_value,
                        step=step,
                        key=name
                    )
                    st.session_state.edited_values[name] = edited_val
                except Exception as e:
                    st.error(f"Error creating slider '{name}': {e}")
            
            elif input_type == "map_multiplier":
                # Read current multiplier from session state or use scaling factor
                current_multiplier = st.session_state.edited_values.get(name, scaling.get('factor',1))
                try:
                    edited_val = st.slider(
                        label=name,
                        min_value=0.5,
                        max_value=2.0,
                        value=current_multiplier,
                        step=0.1,
                        key=name
                    )
                    st.session_state.edited_values[name] = edited_val
                except Exception as e:
                    st.error(f"Error creating map_multiplier slider '{name}': {e}")
            
            elif input_type == "map_editor":
                if rows == 0 or columns == 0:
                    st.warning(f"Map '{name}' has invalid rows or columns.")
                    continue
                # Calculate cell_length and cell_data_type
                cell_length = length // (rows * columns)
                cell_data_type = get_cell_data_type(cell_length)
                if cell_data_type is None:
                    st.error(f"Unsupported cell length {cell_length} in map '{name}'. Skipping.")
                    continue
                
                # Read current map data from binary
                map_data = []
                for row in range(rows):
                    row_data = []
                    for col in range(columns):
                        # Calculate offset for each cell if applicable
                        # For simplicity, assume contiguous storage row-wise
                        cell_offset = int(offset, 16) + (row * columns + col) * cell_length
                        cell_value = read_from_binary(hex(cell_offset), cell_length, cell_data_type, sign_type, scaling)
                        row_data.append(cell_value)
                    map_data.append(row_data)
                
                df = pd.DataFrame(map_data, columns=[f"Col {i+1}" for i in range(columns)])
                
                # Determine which columns are editable
                if isinstance(editable_columns, list):
                    disabled_columns = [not (i in editable_columns) for i in range(columns)]
                elif isinstance(editable_columns, str) and editable_columns.lower() == "all":
                    disabled_columns = [False] * columns
                else:
                    # Default to all columns editable if format is unexpected
                    disabled_columns = [False] * columns
                    st.warning(f"Unexpected format for 'editable_columns' in map '{name}'. All columns set to editable.")
                
                # Note: Streamlit's st.data_editor does not support per-cell disabling.
                # Only entire columns can be disabled.
                try:
                    edited_df = st.data_editor(
                        df,
                        num_rows="dynamic",
                        use_container_width=True,
                        key=name,
                        disabled=disabled_columns
                    )
                    st.session_state.edited_values[name] = edited_df
                except Exception as e:
                    st.error(f"Error creating data editor for map '{name}': {e}")
            
            elif input_type == "readonly":
                # Display the value without allowing edits
                current_value = read_from_binary(offset, length, data_type, sign_type, scaling)
                if current_value is None:
                    current_value = default
                st.text(f"Value: {current_value}")
            
            else:
                st.warning(f"Unsupported input type: {input_type}")
    
    st.header("Map Groups")
    for group in json_data.get("map_groups", []):
        group_name = group.get("group_name", "Unnamed Group")
        process_maps(group.get("maps", []), group_name=group_name)
        # Handle control sliders if any
        control_slider = group.get("control_slider")
        if control_slider:
            cs_name = control_slider.get("name")
            cs_description = control_slider.get("description", "")
            cs_min = control_slider.get("min_value")
            cs_max = control_slider.get("max_value")
            cs_step = control_slider.get("step", 0.1)
            cs_default = control_slider.get("default_value", 1.0)
            
            # Validate control slider parameters
            if cs_min is None or cs_max is None or cs_step is None:
                st.error(f"Control slider '{cs_name}' is missing 'min_value', 'max_value', or 'step'. Skipping.")
                continue
            if not isinstance(cs_min, (int, float)) or not isinstance(cs_max, (int, float)) or not isinstance(cs_step, (int, float)):
                st.error(f"Control slider '{cs_name}' has invalid 'min_value', 'max_value', or 'step' types. Skipping.")
                continue
            if cs_min > cs_max:
                st.error(f"Control slider '{cs_name}' has 'min_value' greater than 'max_value'. Skipping.")
                continue
            
            st.subheader(cs_name)
            st.write(cs_description)
            current_cs = st.session_state.edited_values.get(cs_name, cs_default)
            # Ensure current_cs is within min and max
            current_cs = max(cs_min, min(cs_max, current_cs))
            try:
                edited_cs = st.slider(
                    label=cs_name,
                    min_value=cs_min,
                    max_value=cs_max,
                    value=current_cs,
                    step=cs_step,
                    key=cs_name
                )
                st.session_state.edited_values[cs_name] = edited_cs
            except Exception as e:
                st.error(f"Error creating control slider '{cs_name}': {e}")
    
    st.header("Editable Maps")
    process_maps(json_data.get("editable_maps", []), group_name="Editable Maps")
    
    # Save Button
    if st.button("Save Changes"):
        try:
            # Apply edited values to binary_data
            # Process map_groups
            for group in json_data.get("map_groups", []):
                for map_item in group.get("maps", []):
                    name = map_item.get("name")
                    input_type = map_item.get("input_type")
                    data_type = map_item.get("data_type")
                    sign_type = map_item.get("sign_type", "unsigned")
                    scaling = map_item.get("scaling", {})
                    offset = map_item.get("offset")
                    length = map_item.get("length")
                    
                    if input_type == "slider":
                        value = st.session_state.edited_values.get(name, map_item.get("default_value"))
                        write_to_binary(offset, length, data_type, sign_type, value, scaling)
                    
                    elif input_type == "map_multiplier":
                        multiplier = st.session_state.edited_values.get(name, scaling.get("factor",1))
                        # Apply multiplier to all related maps
                        for related_map in group.get("maps", []):
                            if related_map.get("input_type") == "map_multiplier":
                                continue
                            related_data_type = related_map.get("data_type")
                            if related_data_type == "array":
                                # Do not write scaling factors back to binary
                                st.warning(f"Skipping writing scaling factor for map '{related_map.get('name')}' as it has data_type 'array'")
                                # Update scaling factor in JSON to be used in display
                                related_map_scaling = related_map.get("scaling", {})
                                original_factor = related_map_scaling.get("factor",1)
                                new_factor = original_factor * multiplier
                                related_map_scaling['factor'] = new_factor
                                related_map['scaling'] = related_map_scaling
                                # Optionally, store new_factor in session_state or elsewhere
                            else:
                                # For non-array data_types, update scaling factor in binary
                                map_name = related_map.get("name")
                                map_scaling = related_map.get("scaling", {})
                                original_factor = map_scaling.get("factor",1)
                                new_factor = original_factor * multiplier
                                map_scaling['factor'] = new_factor
                                related_map['scaling'] = map_scaling
                                # Update binary with new scaling factor
                                write_to_binary(related_map.get("offset"), related_map.get("length"), related_map.get("data_type"), related_map.get("sign_type", "unsigned"), new_factor, {})
                    
                    elif input_type == "map_editor":
                        edited_df = st.session_state.edited_values.get(name)
                        if edited_df is not None:
                            rows = map_item.get("map_dimension", {}).get("rows", 0)
                            columns = map_item.get("map_dimension", {}).get("columns", 0)
                            cell_length = length // (rows * columns)
                            cell_data_type = get_cell_data_type(cell_length)
                            if cell_data_type is None:
                                st.error(f"Unsupported cell length {cell_length} in map '{name}'. Skipping.")
                                continue
                            for r in range(rows):
                                for c in range(columns):
                                    cell_value = edited_df.iat[r, c]
                                    # Calculate cell offset
                                    cell_offset = int(offset, 16) + (r * columns + c) * cell_length
                                    write_to_binary(hex(cell_offset), cell_length, cell_data_type, sign_type, cell_value, scaling)
                    
                    # Add other input_types as needed
            
                # Handle control sliders
                control_slider = group.get("control_slider")
                if control_slider:
                    cs_name = control_slider.get("name")
                    cs_value = st.session_state.edited_values.get(cs_name, control_slider.get("default_value", 1.0))
                    multiplier = cs_value
                    for map_item in group.get("maps", []):
                        if map_item.get("input_type") in ["map_editor", "map_multiplier"]:
                            related_data_type = map_item.get("data_type")
                            if related_data_type == "array":
                                # Do not write scaling factors back to binary
                                st.warning(f"Skipping writing scaling factor for map '{map_item.get('name')}' as it has data_type 'array'")
                                # Update scaling factor in JSON to be used in display
                                map_scaling = map_item.get("scaling", {})
                                original_factor = map_scaling.get("factor",1)
                                new_factor = original_factor * multiplier
                                map_scaling['factor'] = new_factor
                                map_item['scaling'] = map_scaling
                            else:
                                # For non-array data_types, update scaling factor in binary
                                map_scaling = map_item.get("scaling", {})
                                original_factor = map_scaling.get("factor",1)
                                new_factor = original_factor * multiplier
                                map_scaling['factor'] = new_factor
                                map_item['scaling'] = map_scaling
                                write_to_binary(map_item.get("offset"), map_item.get("length"), map_item.get("data_type"), map_item.get("sign_type", "unsigned"), new_factor, {})
        
        # Process editable_maps
            for editable_map in json_data.get("editable_maps", []):
                name = editable_map.get("name")
                input_type = editable_map.get("input_type")
                data_type = editable_map.get("data_type")
                sign_type = editable_map.get("sign_type", "unsigned")
                scaling = editable_map.get("scaling", {})
                offset = editable_map.get("offset")
                length = editable_map.get("length")
                
                if input_type == "slider":
                    value = st.session_state.edited_values.get(name, editable_map.get("default_value"))
                    write_to_binary(offset, length, data_type, sign_type, value, scaling)
        
        # Provide the modified binary for download
            st.success("Changes applied successfully.")
            modified_binary = BytesIO(binary_data)
            st.download_button(
                label="Download Modified Binary",
                data=modified_binary,
                file_name="modified_binary.bin",
                mime="application/octet-stream"
            )
        except Exception as e:
            st.error(f"An unexpected error occurred while saving changes: {e}")
else:
    st.info("Please upload both JSON and binary files to proceed.")
