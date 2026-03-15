from callable import run_batch_directory
from utils.get_Cur_FY import get_current_year_quarter

result = run_batch_directory(
    directory="D:\AUTOMATION_FILE\AUTOMATION_2026-03-02",
    quarter=get_current_year_quarter(),
    output_dir="D:\AUTOMATION_FILE",
    output_filename="all_platforms.xlsx",
    debug=True
)

print("Wrote:", result["output_path"])
print("By category:", result["by_category"])
print("Failures:", result["failures"])