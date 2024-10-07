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
uploaded_binary = st.file_uploader("Upload Binary File", type=["bin", "dat", "bin"])

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
    
    # Function to write a value to binary data
    def write_to_binary(offset_hex, length, data_type, sign_type, value, scaling):
        offset = int(offset_hex, 16)
        if offset + length > binary_size:
            st.error(f"Offset {offset_hex} with length {length} exceeds binary file size.")
            return
        # Reverse scaling if necessary
        if scaling:
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
        offset = int(offset_hex, 16)
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
            # Apply scaling
            if scaling:
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
                # Read current value from binary
                current_value = read_from_binary(offset, length, data_type, sign_type, scaling)
                if current_value is None:
                    current_value = default
                edited_val = st.slider(
                    label=name,
                    min_value=min_val,
                    max_value=max_val,
                    value=current_value,
                    step=step,
                    key=name
                )
                st.session_state.edited_values[name] = edited_val
            
            elif input_type == "map_multiplier":
                # Read current multiplier from binary if applicable, else use default
                current_multiplier = st.session_state.edited_values.get(name, scaling.get('factor',1))
                edited_val = st.slider(
                    label=item.get("control_slider", {}).get("description", name),
                    min_value=0.5,
                    max_value=2.0,
                    value=current_multiplier,
                    step=0.1,
                    key=name
                )
                st.session_state.edited_values[name] = edited_val
            
            elif input_type == "map_editor":
                # Read current map data from binary
                map_data = []
                for row in range(rows):
                    row_data = []
                    for col in range(columns):
                        # Calculate offset for each cell if applicable
                        # For simplicity, assume contiguous storage row-wise
                        cell_offset = int(offset, 16) + (row * columns + col) * (length // (rows * columns))
                        cell_value = read_from_binary(hex(cell_offset), length // (rows * columns), data_type, sign_type, scaling)
                        row_data.append(cell_value)
                    map_data.append(row_data)
                
                df = pd.DataFrame(map_data, columns=[f"Col {i+1}" for i in range(columns)])
                
                # Determine which columns or regions are editable
                if editable_columns:
                    editable = [False] * columns
                    for col in editable_columns:
                        if isinstance(col, int):
                            editable[col] = True
                    def make_editable(val, col_idx):
                        if editable[col_idx]:
                            return val
                        else:
                            return val
                    edited_df = st.data_editor(
                        df,
                        num_rows="dynamic",
                        use_container_width=True,
                        key=name,
                        disabled=[not editable[i] for i in range(columns)]
                    )
                    st.session_state.edited_values[name] = edited_df
                elif editable_region:
                    # Editable region based on start_row, end_row, start_column, end_column
                    start_row = editable_region.get("start_row", 0)
                    end_row = editable_region.get("end_row", rows-1)
                    start_col = editable_region.get("start_column", 0)
                    end_col = editable_region.get("end_column", columns-1)
                    def is_editable(r, c):
                        return start_row <= r <= end_row and start_col <= c <= end_col
                    edited_df = st.data_editor(
                        df,
                        num_rows="dynamic",
                        use_container_width=True,
                        key=name,
                        disabled=lambda r, c: not is_editable(r, c)
                    )
                    st.session_state.edited_values[name] = edited_df
                else:
                    # No editable fields
                    st.dataframe(df)
            
            elif input_type == "readonly":
                # Display the value without allowing edits
                current_value = read_from_binary(offset, length, data_type, sign_type, scaling)
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
            st.subheader(cs_name)
            st.write(cs_description)
            current_cs = st.session_state.edited_values.get(cs_name, cs_default)
            edited_cs = st.slider(
                label=cs_name,
                min_value=cs_min,
                max_value=cs_max,
                value=current_cs,
                step=cs_step,
                key=cs_name
            )
            st.session_state.edited_values[cs_name] = edited_cs
    
    st.header("Editable Maps")
    process_maps(json_data.get("editable_maps", []), group_name="Editable Maps")
    
    # Save Button
    if st.button("Save Changes"):
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
                        for r in range(rows):
                            for c in range(columns):
                                cell_value = edited_df.iat[r, c]
                                # Calculate cell offset
                                cell_offset = int(offset, 16) + (r * columns + c) * (length // (rows * columns))
                                write_to_binary(hex(cell_offset), length // (rows * columns), data_type, sign_type, cell_value, scaling)
                
                # Add other input_types as needed
            
            # Handle control sliders
            control_slider = group.get("control_slider")
            if control_slider:
                cs_name = control_slider.get("name")
                cs_input_type = control_slider.get("input_type")
                cs_min = control_slider.get("min_value")
                cs_max = control_slider.get("max_value")
                cs_step = control_slider.get("step", 0.1)
                cs_default = control_slider.get("default_value", 1.0)
                cs_value = st.session_state.edited_values.get(cs_name, cs_default)
                # Apply the multiplier to all related maps
                multiplier = cs_value
                for map_item in group.get("maps", []):
                    if map_item.get("input_type") in ["map_editor", "map_multiplier"]:
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
else:
    st.info("Please upload both JSON and binary files to proceed.")
