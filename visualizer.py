#!/usr/bin/env python3
import json
import sys
import os
from datetime import datetime
import argparse
import re

class AgentStepsVisualizer:
    def __init__(self):
        self.css = """
            body { 
                font-family: Arial, sans-serif; 
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .completion-card {
                background: white;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .completion-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 1px solid #eee;
            }
            .completion-id {
                font-size: 1.1em;
                color: #2c3e50;
            }
            .timestamp {
                color: #666;
                font-size: 0.9em;
            }
            .message-content {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin: 10px 0;
                white-space: pre-wrap;
            }
            .tool-calls {
                margin: 15px 0;
            }
            .tool-call {
                background: #f8f9fa;
                border-left: 4px solid #007bff;
                padding: 15px;
                margin: 10px 0;
                border-radius: 0 4px 4px 0;
            }
            .tool-call-header {
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
            }
            .arguments {
                background: #272822;
                color: #f8f8f2;
                padding: 10px;
                border-radius: 4px;
                font-family: monospace;
                overflow-x: auto;
            }
            .usage-info {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin-top: 15px;
                font-size: 0.9em;
            }
            .usage-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 10px;
                margin-top: 10px;
            }
            .usage-item {
                padding: 8px;
                background: white;
                border-radius: 4px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .badge {
                display: inline-block;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 0.8em;
                font-weight: bold;
            }
            .badge-blue { background: #e3f2fd; color: #1565c0; }
            .badge-green { background: #e8f5e9; color: #2e7d32; }
            .badge-purple { background: #f3e5f5; color: #7b1fa2; }
            .collapsible {
                cursor: pointer;
                padding: 10px;
                width: 100%;
                border: none;
                text-align: left;
                outline: none;
                font-size: 15px;
                background: #f1f1f1;
                border-radius: 4px;
                margin: 5px 0;
            }
            .active, .collapsible:hover {
                background-color: #e9ecef;
            }
            .content {
                padding: 0 18px;
                display: none;
                overflow: hidden;
                background-color: white;
            }
        """

    def format_timestamp(self, timestamp):
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    def create_usage_section(self, usage):
        html = ['<div class="usage-info">']
        html.append('<h4>Usage Statistics:</h4>')
        html.append('<div class="usage-grid">')
        
        # Basic token counts
        for key in ['completion_tokens', 'prompt_tokens', 'total_tokens']:
            if key in usage:
                html.append(f'<div class="usage-item"><strong>{key.replace("_", " ").title()}:</strong> {usage[key]}</div>')
        
        # Detailed token information
        if 'completion_tokens_details' in usage:
            details = usage['completion_tokens_details']
            html.append('<div class="usage-item"><strong>Completion Details:</strong>')
            for key, value in details.items():
                html.append(f'<div>{key.replace("_", " ").title()}: {value}</div>')
            html.append('</div>')
            
        if 'prompt_tokens_details' in usage:
            details = usage['prompt_tokens_details']
            html.append('<div class="usage-item"><strong>Prompt Details:</strong>')
            for key, value in details.items():
                html.append(f'<div>{key.replace("_", " ").title()}: {value}</div>')
            html.append('</div>')
            
        html.append('</div></div>')
        return '\n'.join(html)

    def create_tool_calls_section(self, tool_calls):
        if not tool_calls:
            return ''
            
        html = ['<div class="tool-calls">']
        html.append('<h4>Tool Calls:</h4>')
        
        for call in tool_calls:
            html.append('<div class="tool-call">')
            html.append('<div class="tool-call-header">')
            html.append(f'<span class="badge badge-blue">{call["function"]["name"]}</span>')
            html.append(f'<span class="badge badge-purple">ID: {call["id"]}</span>')
            html.append('</div>')
            
            # Format arguments as JSON
            try:
                if isinstance(call["function"]["arguments"], str):
                    args = json.loads(call["function"]["arguments"])
                else:
                    args = call["function"]["arguments"]
                formatted_args = json.dumps(args, indent=2)
            except:
                formatted_args = str(call["function"]["arguments"])
                
            html.append('<div class="arguments">')
            html.append(f'<pre>{formatted_args}</pre>')
            html.append('</div>')
            html.append('</div>')
            
        html.append('</div>')
        return '\n'.join(html)

    def generate_html(self, json_path):
        try:
            # Read and parse JSON
            with open(json_path, 'r') as f:
                content = f.read()
            
            # Find the JSON array
            array_start = content.find('[')
            array_end = content.rfind(']') + 1
            if array_start == -1 or array_end <= 0:
                raise ValueError("Could not find JSON array")
                
            data = json.loads(content[array_start:array_end])
            
            # Get title
            title = os.path.splitext(os.path.basename(json_path))[0].replace('_', ' ').title()
            
            # Generate HTML
            html = [
                '<!DOCTYPE html>',
                '<html>',
                '<head>',
                f'<title>{title}</title>',
                '<meta charset="UTF-8">',
                '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
                f'<style>{self.css}</style>',
                '</head>',
                '<body>',
                '<div class="container">',
                f'<h1>{title}</h1>'
            ]
            
            for completion in data:
                # Start completion card
                html.append('<div class="completion-card">')
                
                # Header section
                html.append('<div class="completion-header">')
                html.append(f'<div class="completion-id">ID: {completion["id"]}</div>')
                html.append(f'<div class="timestamp">{self.format_timestamp(completion["created"])}</div>')
                html.append('</div>')
                
                # Model info
                if "model" in completion:
                    html.append(f'<div class="badge badge-green">Model: {completion["model"]}</div>')
                
                # Process choices
                for choice in completion.get('choices', []):
                    message = choice.get('message', {})
                    
                    # Message content
                    if message.get('content'):
                        html.append(f'<div class="message-content">{message["content"]}</div>')
                    
                    # Tool calls
                    if message.get('tool_calls'):
                        html.append(self.create_tool_calls_section(message['tool_calls']))
                
                # Usage information
                if 'usage' in completion:
                    html.append(self.create_usage_section(completion['usage']))
                
                html.append('</div>')  # End completion card
            
            # Close HTML
            html.extend([
                '</div>',
                '<script>',
                'var coll = document.getElementsByClassName("collapsible");',
                'for (var i = 0; i < coll.length; i++) {',
                '    coll[i].addEventListener("click", function() {',
                '        this.classList.toggle("active");',
                '        var content = this.nextElementSibling;',
                '        if (content.style.display === "block") {',
                '            content.style.display = "none";',
                '        } else {',
                '            content.style.display = "block";',
                '        }',
                '    });',
                '}',
                '</script>',
                '</body>',
                '</html>'
            ])
            
            # Write output
            output_path = os.path.splitext(json_path)[0] + '.html'
            with open(output_path, 'w') as f:
                f.write('\n'.join(html))
            
            print(f"Generated HTML file: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error processing {json_path}: {str(e)}")
            return None

def main():
    parser = argparse.ArgumentParser(description='Generate HTML visualization for agent steps JSON file')
    parser.add_argument('json_path', help='Path to the JSON file')
    parser.add_argument('--open', action='store_true', help='Open the generated HTML file in browser')
    
    args = parser.parse_args()
    
    visualizer = AgentStepsVisualizer()
    output_path = visualizer.generate_html(args.json_path)
    
    if output_path:
        if args.open:
            os.system(f"xdg-open {output_path}")
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
