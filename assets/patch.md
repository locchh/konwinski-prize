### **Complete List of Unified Diff Patch Components**

Here is a more detailed breakdown of all possible components:

1. **File Headers**
   - Indicate the original (`---`) and modified (`+++`) file names, and sometimes include timestamps.
   - Example:
     ```diff
     --- example.txt    2025-03-03 12:00:00
     +++ example.txt    2025-03-03 12:01:00
     ```

2. **Hunk Headers (Hunk Range Information)**
   - Start with `@@ -start,count +start,count @@` and may include optional function names in code diffs.
   - Example:
     ```diff
     @@ -1,4 +1,4 @@
     ```
   - **Details:**
     - `-1,4`: Original file starts at line **1** and affects **4** lines.
     - `+1,4`: Modified file starts at line **1** and affects **4** lines.

3. **Context Lines**
   - Lines that remain unchanged to provide context.
   - Example:
     ```diff
     Hello, world!
     It has multiple lines.
     ```

4. **Removed Lines (`-`)**
   - Lines that existed in the original file but were deleted.
   - Example:
     ```diff
     -This is a simple text file.
     ```

5. **Added Lines (`+`)**
   - Lines that were introduced in the modified file.
   - Example:
     ```diff
     +This is a modified text file.
     ```

6. **File Mode Changes** (Optional, mainly in Git patches)
   - Used when file permissions (e.g., executable bit) are changed.
   - Example:
     ```diff
     old mode 100644
     new mode 100755
     ```

7. **File Rename or Copy Information** (Optional, mainly in Git patches)
   - Indicates that a file was renamed or copied.
   - Example:
     ```diff
     rename from old_file.txt
     rename to new_file.txt
     ```

8. **Binary File Changes** (Optional)
   - When the diff is for binary files (e.g., images, compiled files), it may indicate that the file is binary.
   - Example:
     ```diff
     Binary files example.png and example.png differ
     ```

9. **No Newline at End of File (`\ No newline at end of file`)**
   - Indicates that one of the files does not end with a newline character.
   - Example:
     ```diff
     +New line added
     \ No newline at end of file
     ```

10. **Index Line (Git-specific)**
    - Used in Git patches to show the SHA-1 hash of the file before and after the change.
    - Example:
      ```diff
      index a1b2c3d..e4f5g6h 100644
      ```

11. **Function Context (for Code Diffs)**
    - Some diff tools include function names or code context in hunks.
    - Example (C function diff):
      ```diff
      @@ -10,6 +10,7 @@ int add(int a, int b) {
      ```

---

### **Example of a More Complex Patch (Including Rename and File Mode Change)**
```diff
diff --git a/old_file.txt b/new_file.txt
rename from old_file.txt
rename to new_file.txt
old mode 100644
new mode 100755
index a1b2c3d..e4f5g6h 100644
--- old_file.txt
+++ new_file.txt
@@ -1,4 +1,4 @@
 Hello, world!
-This is a simple text file.
+This is a modified text file.
 It has multiple lines.
-Goodbye!
+See you later!
\ No newline at end of file
```

---

### **Summary of Additional Components**
| Component Name                 | Description |
|--------------------------------|-------------|
| **File Mode Changes**          | Shows if file permissions changed. |
| **File Rename/Copy Info**      | Shows if a file was renamed or copied. |
| **Binary File Change Notice**  | Indicates changes in binary files. |
| **No Newline Warning**         | Marks missing newline at file end. |
| **Index Line (Git)**           | Shows Git SHA-1 hash of the file. |
| **Function Context (Code Diffs)** | Displays the surrounding function in code changes. |