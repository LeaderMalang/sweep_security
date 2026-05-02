import ast

with open('services/notification_service.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if line.strip().startswith('async def wizard_') and '(self, message: types.Message, state: FSMContext):' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(f"{indent}    if message.text and message.text.startswith('/'):\n")
        new_lines.append(f"{indent}        await message.answer(\"⚠️ Please use /cancel to exit the current setup process before running another command.\")\n")
        new_lines.append(f"{indent}        return\n")

with open('services/notification_service.py', 'w') as f:
    f.writelines(new_lines)
