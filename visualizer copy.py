import json

def generate_html(json_file, output_file):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>JSON Visualization</title>
        <style>
            body { font-family: Arial, sans-serif; }
            table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h2>JSON Data Visualization</h2>
        <table>
            <tr>
                <th>ID</th>
                <th>Model</th>
                <th>Tool Calls</th>
            </tr>
    """

    for entry in data:
        entry_id = entry.get("id", "N/A")
        model = entry.get("model", "N/A")

        tool_calls_html = "<ul>"
        for choice in entry.get("choices", []):
            message = choice.get("message", {})
            tool_calls = message.get("tool_calls", [])  # Ensure it’s a list
            
            if tool_calls:
                for tool_call in tool_calls:
                    func_name = tool_call["function"]["name"]
                    func_args = tool_call["function"]["arguments"]
                    tool_calls_html += f"<li><strong>{func_name}</strong>: {func_args}</li>"
            else:
                tool_calls_html += "<li>No tool calls</li>"

        tool_calls_html += "</ul>"

        html_content += f"""
            <tr>
                <td>{entry_id}</td>
                <td>{model}</td>
                <td>{tool_calls_html}</td>
            </tr>
        """

    html_content += """
        </table>
    </body>
    </html>
    """

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

# Run the function with your JSON file
generate_html("agent_steps_astropy__astropy-16830.json", "output.html")
