from typing import List, Literal
import re
from difflib import unified_diff
import requests
import os
from datetime import datetime
import json
from Levenshtein import ratio
 


def build_new_file(orig_file, patches):
    newfile = ''
    last_end_idx = 0
    if 'start_idx' not in patches[0]:
        raise ValueError("Failed to build diff file: No patch match found")
    patches.sort(key = lambda x: x['start_idx'])
    for patch in patches:
        start_idx = patch['start_idx']
        newfile += orig_file[last_end_idx:start_idx] + patch['new_text']
        # end = patch[1]-1
        last_end_idx = start_idx + len(patch['orig_text'])
    newfile += orig_file[last_end_idx:]
    return newfile


def build_diff(orig_file, new_file, file_name):
    diff = unified_diff(
        orig_file.splitlines(), new_file.splitlines(),
        fromfile=f"a/{file_name}", tofile=f"b/{file_name}", lineterm=""
    )
    return "\n".join(diff)


class CodeGPT_Patcher:
    
    # Constructor based on swe_bench dataframe object, API_URL, and SECRET_KEY
    def __init__(self, swe_bench_dataframe, api_url, secret_key, model: Literal['claude-4-opus-vertex', 'claude-3.7-vertex', 'llama-4-maverick-17b-groq'] ="llama-4-maverick-17b-groq"):
        
        row = swe_bench_dataframe
        self.model = model
        self.df = row
        self.repo = row.repo
        self.base_commit = row.base_commit
        self.problem_statement  = row.problem_statement
        self.hints_text  = row.hints_text
        self.graph_id = row.graph_id
        self.instance_id = row.name
        self.api_url = api_url
        self.secret_key = secret_key
        self.message_queue = []
        self.history = []
        self.answers = []
        self.patches = []
        self.diffs = []
        self.requery = False
        self.requery_validator = False
        self.files_not_found = []

        self.data = {
            "agentId": os.environ['AGENT_ID'], # This is an agent without prompt
            "graphId": "myGraphId",
            "stream": False,
            "format": "text",
            "messages": [],
            "agentType": "patcher",
            "model": self.model,
        }

        self.orig_files = dict()
        self.new_files = dict()
        self.usage = {'input_tokens': 0, 'output_tokens': 0}

    def full_query_LLM(self):
        print(f"f{self.repo}: Querying LLM...\n")
        self.query_LLM()
        self.parse_LLM_solution()
        self.process_patches()
        if self.requery:
            print(f"f{self.repo}: Requerying LLM...\n")
            self.requery_LLM()
            self.parse_LLM_solution()
            self.process_patches()


    def query_LLM(self):
        self.files_not_found = []
        prompt = f"<issue>\n{self.problem_statement}\n</issue>"
        prompt += f"\n\n<hints>\n{self.hints_text}\n</hints>" if self.hints_text else ""
        prompt += f"\n\nRemember: Pay attention to the new content you add, as everything must be well-defined.\nRemember to pay special attention to the traceback or the actual outcome."

        self.data['graphId'] = self.graph_id
        self.data['format'] = 'json'
        self.data['messages'] = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        self.history.append(self.data['messages'][-1])
        self.data["agentType"] = "patcher"

        response = requests.post(f"{self.api_url}/api/v1/chat/completions", 
                            headers={"Authorization": f"Bearer {self.secret_key}"},
                            json=self.data)
        if response.ok:
            # answer = response.text.replace('\\n', '\n')
            messages = response.json()['choices']
            self.message_queue.append(messages)
            self.answers.append(messages[-1]['content'][0]['text'] if self.model != 'llama-4-maverick-17b-groq' else messages[-1]['content'])
            self.history.append({
                "role": "assistant",
                "content": self.answers[-1]
            })

        else:
            error = response.json()
            raise Exception(f"LLM query failed: {json.dumps(error)}")
        self.validate_files()

    def evaluate_LLM(self):
        prompt = f"<issue>\n{self.problem_statement}\n</issue>"
        prompt += f"\n\n<hints>\n{self.hints_text}\n</hints>" if self.hints_text else ""
        prompt += "\n\nThe patcher agent answered with the following:" if not self.requery_validator else "\n\nYou previously answered with the following:"
        prompt += f"\n<patcher_answer>\n{self.answers[-1]}\n</patcher_answer>\n"
        prompt += '\nBUT, files ' + ', '.join(self.files_not_found) + ' do not exist in the repository, remember to pass the complete file path and use only the files that are part of the repository. ' if self.files_not_found else ''
        self.data['graphId'] = self.graph_id
        self.data['format'] = 'json'
        self.data['messages'] = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        self.history.append(self.data['messages'][-1])
        self.data["agentType"] = "validator"

        response = requests.post(f"{self.api_url}/api/v1/chat/completions", 
                            headers={"Authorization": f"Bearer {self.secret_key}"},
                            json=self.data)
        if response.ok:
            # answer = response.text.replace('\\n', '\n')
            messages = response.json()['choices']
            self.message_queue.append(messages)
            self.answers.append(messages[-1]['content'][0]['text'] if self.model != 'llama-4-maverick-17b-groq' else messages[-1]['content'])
            self.history.append({
                "role": "assistant",
                "content": self.answers[-1]
            })

        else:
            error = response.json()
            raise Exception(f"LLM query failed: {json.dumps(error)}")
        self.validate_files()
        self.requery_validator = True if self.files_not_found else False

    def requery_LLM(self):
        prompt = 'Files ' + ', '.join(self.files_not_found) + ' do not exist in the repository, remember to pass the complete file path. ' if self.files_not_found else ''
        prompt = f"""I previously asked you about an issue, but the system had problems using your answer. Please pay special attention to comments and identation in the text you want me to replace, since I need the exact match to apply the patch. Also, remember to open and close the answer using the <replace> tags. Note that I DON'T HAVE DIRECT ACCESS TO EDIT THE CODE MANUALLY, so you must provide me with the exact text to replace.\n"""
        for file_name in self.patches[-1].keys():
            give_file = False
            newprompt = ''
            for patch_idx, patch in enumerate(self.patches[-1][file_name]):
                if patch['num_matches'] <= 1:
                    if newprompt == '':
                        newprompt += f"In file: {file_name}:\n"
                    newprompt += f"""Patch {patch_idx+1}: I couldn't find the @@REPLACE@@ marker:\n<marker>\n{patch['orig_text']}\n</marker>\n"""
                    # newprompt += f"""The best match I found in the original file was:\n<marker>\n{patch['match_segment']}\n</marker>\nEnsure proper identation since the match must be exact!"""
                    give_file = True
                if patch['num_matches'] > 1:
                    if newprompt == '':
                        newprompt += f"In file: {file_name}:\n"
                    newprompt += f"""Patch {patch_idx+1}: I found multiple matches for @@REPLACE@@ block:\n<marker>\n{patch['orig_text']}\n<\marker>\nCan you give me more context lines?"""
            if give_file:
                try:
                    newprompt += f"""<actual_file>\n{self.orig_files[file_name]}\n</actual_file>"""
                except:
                    newprompt += f"""<actual_file>File {file_name} does not exists in the repo</actual_file>"""
            prompt += newprompt + "\n"

        self.data['graphId'] = self.graph_id
        self.data['format'] = 'json'
        self.data['messages'] = [
            {
                "role": "user",
                "content": f"<issue>\n{self.problem_statement}\n</issue>\n\n<hints>\n{self.hints_text}\n</hints>"
            },
            {
                "role": "assistant",
                "content": self.answers[-1]
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        self.data["agentType"] = "patchFixer"

        response = requests.post(f"{self.api_url}/api/v1/chat/completions", 
                            headers={"Authorization": f"Bearer {self.secret_key}"},
                            json=self.data)
        if response.ok:
            # answer = response.text.replace('\\n', '\n')
            messages = response.json()['choices']
            self.message_queue.append(messages)
            self.answers.append(messages[-1]['content'][0]['text'] if self.model != 'llama-4-maverick-17b-groq' else messages[-1]['content'])
            self.history.append({
                "role": "assistant",
                "content": self.answers[-1]
            })
        else:
            error = response.json()
            raise Exception(f"LLM query failed: {json.dumps(error)}")
        self.validate_files()
        

    def custom_query_LLM(self, prompt, use_history=True):
        self.data['graphId'] = self.graph_id
        self.data['format'] = 'json'
        if use_history:
            self.data['messages'] = self.history.copy()
        self.data['messages'].append({
                "role": "user",
                "content": prompt
        })
        self.history.append(self.data['messages'][-1])

        response = requests.post(f"{self.api_url}/api/v1/chat/completions", 
                                headers={"Authorization": f"Bearer {self.secret_key}"},
                                json=self.data)
        if response.ok:
            # answer = response.text.replace('\\n', '\n')
            messages = response.json()['choices']
            self.message_queue.append(messages)
            self.answers.append(messages[-1]['content'][0]['text'] if self.model != 'llama-4-maverick-17b-groq' else messages[-1]['content'])
            self.history.append({
                "role": "assistant",
                "content": self.answers[-1]
            })
            # print(self.answers[-1])

        else:
            error = response.json()
            raise Exception(f"LLM query failed: {json.dumps(error)}")


    def validate_files(self):
        self.files_not_found = []
        for match in re.finditer(r"<replace file=(.*?)>(.*?)</replace>", self.answers[-1], re.DOTALL):
            file_name = match.group(1).strip().strip("'\"").split('::')[0]
            # Check if file_name exists in the repository
            try: 
                self.request_github_file(file_name)
            except:
                self.files_not_found.append(file_name)


    def parse_LLM_solution(self):
        try:
            self.patches.append(dict())
            for i in range(len(self.answers)-1, -1, -1):
                if list(re.finditer(r"<replace file=(.*?)>(.*?)</replace>", self.answers[i], re.DOTALL)):
                    last_answer_with_patch = self.answers[i]
                    break
            for match in re.finditer(r"<replace file=(.*?)>(.*?)</replace>", last_answer_with_patch, re.DOTALL):
                file_name = match.group(1).strip().strip("'\"").split('::')[0]
                patch_content = self.parse_patch_notation(match.group(2))
                if file_name not in self.patches[-1]:
                    self.patches[-1][file_name] = []
                self.patches[-1][file_name] += patch_content
                # Below should have a failure mode if file isn't found
                self.orig_files[file_name] = self.request_github_file(file_name)
        except Exception as e:
            print(e)
            raise Exception("Failed to parse LLM solution: "+ str(e))

    def process_patches(self):
        SIMILARITY_THRESHOLD = 0.98

        requeries = []

        for file_name, patches in self.patches[-1].items():
            file_content = self.orig_files.get(file_name)
            for patch in patches:
                patch_len = len(patch['orig_text'])
                best_ratio = 0
                best_idx = -1

                if not file_content:
                    patch['num_matches'] = 0
                    requeries.append(True)
                    continue

                # Check each possible position in the file
                for i in range(len(file_content) - patch_len + 1):
                    # Compare patch text with same-length segment from file
                    segment = file_content[i:i + patch_len]
                    match_ratio = ratio(patch['orig_text'], segment)
                    
                    if match_ratio > best_ratio:
                        best_ratio = match_ratio
                        best_idx = i
                        best_segment = file_content[i:i + patch_len]

                patch['match_ratio'] = best_ratio
                patch['match_segment'] = best_segment

                if best_ratio > SIMILARITY_THRESHOLD:
                    patch['start_idx'] = best_idx
                    patch['num_matches'] = 1
                    requeries.append(False)
                else:
                    patch['num_matches'] = 0
                    requeries.append(True)
        self.requery = any(requeries)



    def request_github_file(self, file_path):
        # Construct the raw file URL
        raw_url = f"https://raw.githubusercontent.com/{self.repo}/{self.base_commit}/{file_path}"
        # Send request to fetch file content
        response = requests.get(raw_url)
        # Check if request was successful
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"Invalid github file request\nrepo = {self.repo}, commit = {self.base_commit}, file_path = {file_path}")


    def parse_patch_notation(self, text):
        # pattern = r"@@(\d+),(\d+)@@\n(.*?)@@@@\n(.*?)(?=@@\d+,\d+@@|$)"
        pattern = r"@@REPLACE@@\n(.*?)@@WITH@@\n(.*?)(?=@@|\Z)"
        patches = []
        for match in re.finditer(pattern, text, re.DOTALL):
            patch = dict()
            patch['orig_text'] = match.group(1)
            patch['new_text'] = match.group(2)
            patches.append(patch)
        return patches


    def apply_patch(self):
        latest_patch = self.patches[-1]
        for file_name, filepatch in latest_patch.items():
            new_file = build_new_file(self.orig_files[file_name], filepatch)
            new_diff = build_diff(self.orig_files[file_name], new_file, file_name)
            self.diffs.append(new_diff)

    def save_results(self, run_name):
        if (len(self.diffs) == 0):
            raise Exception('No diffs to save')
        os.makedirs(f"../data/results/{run_name}", exist_ok=True)

        os.makedirs(f"../data/results/{run_name}/diffs", exist_ok=True)
        os.makedirs(f"../data/results/{run_name}/patches", exist_ok=True)
        os.makedirs(f"../data/results/{run_name}/trajs", exist_ok=True)

        with open(f"../data/results/{run_name}/trajs/{self.instance_id}.json", "w") as f:
                f.write(json.dumps(self.message_queue, ensure_ascii=False, indent=4))

        with open(f"../data/results/{run_name}/diffs/{self.instance_id}.diff", "w") as f:
            f.write(combine_patches(list(set(self.diffs))))

        with open(f"../data/results/{run_name}/patches/{self.instance_id}_patches.json", "w") as f:
            f.write(json.dumps(self.patches[-1], ensure_ascii=False, indent=4))

            

def combine_patches(patches):
    """
    Combines multiple git patches into a single patch.
    
    Args:
        patches (list): List of patch strings
    
    Returns:
        str: Combined patch
    """
    # Dictionary to store changes by file
    changes_by_file = {}
    
    for patch in patches:
        # Split patch into lines
        lines = patch.split('\n')
        
        current_file = None
        current_changes = []
        
        for line in lines:
            # Check for file header lines
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                if line.startswith('--- a/'):
                    current_file = line[6:]  # Remove '--- a/' prefix
                continue
            
            # If we have a current file, collect its changes
            if current_file and line:
                if line.startswith('@@'):
                    # Start of a new hunk
                    if current_file not in changes_by_file:
                        changes_by_file[current_file] = []
                    changes_by_file[current_file].append([line])
                elif changes_by_file.get(current_file):
                    # Add change line to current hunk, removing trailing whitespace
                    # If the line starts with +, -, or space, preserve it and strip the rest
                    if line[0] in ['+', '-', ' ']:
                        prefix = line[0]
                        rest = line[1:].rstrip()
                        line = prefix + rest
                    else:
                        line = line.rstrip()
                    changes_by_file[current_file][-1].append(line)
    
    # Combine all changes into a single patch
    combined_patch = []
    for filename, hunks in changes_by_file.items():
        # Add file header
        combined_patch.append(f'--- a/{filename}')
        combined_patch.append(f'+++ b/{filename}')
        
        # Add all hunks
        for hunk in hunks:
            combined_patch.extend(hunk)

    patch = '\n'.join(combined_patch)

    if patch[-1] != '\n':
        patch += '\n'
    
    return patch

def save_patchers_info(patchers: List[CodeGPT_Patcher], name='CodeGPT'):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    jsonl_lines = []
    for n, patcher in enumerate(patchers):
        try:
            jsonl_line = {
                "instance_id": patcher.instance_id,
                "model_name_or_path": name,
                "model_patch": combine_patches(list(set(patcher.diffs)))
            }
            jsonl_lines.append(json.dumps(jsonl_line, ensure_ascii=False))
            # save messages too
            os.makedirs(f"../data/messages/{now}", exist_ok=True)
            with open(f"../data/messages/{now}/{patcher.instance_id}.json", "w") as f:
                f.write(json.dumps(patcher.message_queue, ensure_ascii=False, indent=4))
            with open(f"../data/messages/{now}/{patcher.instance_id}.diff", "w") as f:
                f.write(combine_patches(list(set(patcher.diffs))))
        except Exception as e:
            print(f'Failed to save info for {patcher.instance_id} ({n})')
            raise e
    with open(f"../data/results/{name}__{now}.jsonl", "w") as f:
        f.write("\n".join(jsonl_lines))
    print(f"Saved {len(patchers)} patchers to ../data/results/{name}__{now}.jsonl")
    
