import os

# Specify the root directory to search
root_directory = 'FMOFP'

# Walk through the directory and subdirectories
for root, dirs, files in os.walk(root_directory):
    # Ignore __pycache__ directories
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for file in files:
        if file.endswith('.xml'):
            file_path = os.path.join(root, file)
            try:
                # Check if the file is empty
                with open(file_path, 'r+') as f:
                    content = f.read()
                    if not content:  # The file is empty
                        comment = f'# {file}\n'  # Prepare the comment
                        # Move the file pointer to the start of the file
                        f.seek(0)
                        f.write(comment)  # Write the comment
                        f.truncate()  # Remove the rest of the file content if any
            except Exception as e:
                logger.info(f"Error processing file {file_path}: {str(e)}")

logger.info("Processing complete.")
