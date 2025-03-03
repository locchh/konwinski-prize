import json
from helper import safe_completion

class Agent:

    def __init__ (self, client, tool_schemas, tools_map, messages, model_name, max_iteration=6):

        self.client = client
        self.tool_schemas = tool_schemas
        self.tools_map = tools_map
        self.messages = messages
        self.model_name = model_name
        self.max_iteration = max_iteration
        self.current_iteration = 1
        self.steps = []
        self.file_modifications = {}  # Track file modifications

    def run(self):

        while self.current_iteration <= self.max_iteration:

            print(f"Step {self.current_iteration}")

            # Increase step number
            self.current_iteration +=1

            # Get completion
            completion = safe_completion(self.client,
                             model_name=self.model_name,
                             messages=self.messages,
                             tool_schemas=self.tool_schemas,
                             retries=2
                            )
            
            # Collect steps
            self.steps.append(completion.dict())

            # Check content
            content = completion.choices[0].message.content
            if content:
                print("Assistant:", content)
                # Try to generate patches if solution is found
                if "solution" in content.lower() or "fix" in content.lower():
                    patch_result = self.tools_map["generate_patches"](content)
                    print(patch_result)
                    if "Generated patch file:" in patch_result:
                        break

            # Check tool_calls
            tool_calls = completion.choices[0].message.tool_calls
            if not tool_calls:
                break

            # Execute tools
            for tool_call in tool_calls:

                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                function =self.tools_map[function_name]
                
                # Track file modifications
                if function_name in ["edit_file", "write_to_file"]:
                    file_path = function_args.get("TargetFile")
                    if file_path:
                        self.file_modifications[file_path] = True
                
                result = function(**function_args)


                # Append assistant's tool call response
                self.messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": function_name,
                                "arguments": json.dumps(function_args)
                            }
                        }
                    ]
                })
            
                # Append tool response correctly
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })