"""
Metrics Pipeline - JUnit Test Generation and Branch Coverage Analysis

This script combines:
1. LLM-based JUnit test generation (for branch coverage)
2. Maven test execution with Jacoco coverage collection

Input: Cog_96_12.csv with 'method' column containing Java classes
Output: 
  - coverage_results.csv (detailed results)
  - coverage_summary.csv (summary with percentages)
"""

import os
import sys
import time
import random
import csv
import re
import pandas as pd
import subprocess
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

# LangChain imports for LLM
from langchain_openai import ChatOpenAI
try:
    from langchain.prompts import PromptTemplate
except ImportError:
    from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# PART 1: LLM TEST GENERATION
# =============================================================================

# Setup OpenAI GPT-5
llm = ChatOpenAI(
    model="gpt-5",
    temperature=0.2
)

# Prompt template for test generation
TEST_GENERATION_TEMPLATE = """
You are an expert Java unit test engineer.
Your task: Generate ONLY a full JUnit5 test class (with necessary imports, annotations, and assertions) and with:
{class_name_instruction}

CRITICAL INSTRUCTIONS:
1. Do NOT include or rewrite the method under test in the test file.
2. Do NOT copy the method under test code into the test class.
3. ASSUME the method under test already exists in a separate original class file.
4. The test class should ONLY contain:
   - Package declaration (if needed)
   - Import statements
   - Test class declaration
   - Test methods with @Test annotations
   - Assertions (assertEquals, assertTrue, assertFalse, etc.)
   - Any helper methods needed for testing

5. To test the method, either:
   - Create an instance of the class containing the method and call it
   - Call the method directly if it's static

6. Do NOT add placeholder comments like "// Class containing the method" or "// Method implementation".
7. Generate ONLY executable JUnit5 test code.
8. Do not explain anything. Do not add extra comments beyond what's necessary for test clarity.

COVERAGE-SPECIFIC INSTRUCTIONS:
{coverage_guidance}

The generated tests must maximize {coverage_type} for the given method.
{class_name_instruction}

Method under test (MUT):
{method_under_test}
"""

prompt = PromptTemplate(
    input_variables=["coverage_type", "method_under_test", "class_name_instruction", "coverage_guidance"],
    template=TEST_GENERATION_TEMPLATE
)

chain = prompt | llm


def get_coverage_guidance(coverage_type):
    """Generate coverage-specific guidance based on coverage type."""
    
    guidance = {
        "branch": """
FOR BRANCH COVERAGE:
- Test BOTH true and false paths of every conditional (if, else, switch, ternary, loops)
- For nested conditions, cover all branch combinations
- For loops, test: zero iterations, one iteration, and multiple iterations
- Ensure every decision point has tests for all possible outcomes
""",
        
        "line": """
FOR LINE COVERAGE:
- Execute EVERY line in the method at least once
- Reach all code blocks: if-else branches, switch cases, loop bodies, exception handlers
- Ensure no line remains unexecuted across your test suite
"""
    }
    
    return guidance.get(coverage_type, guidance["branch"])


def extract_class_name(java_code: str) -> str:
    """Extract class name from Java source code."""
    class_pattern = r'(?:public\s+)?(?:abstract\s+)?(?:final\s+)?class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    match = re.search(class_pattern, java_code)
    if match:
        return match.group(1)
    return "UnknownClass"


def strip_markdown_code_blocks(code: str) -> str:
    """Remove markdown code block formatting from LLM output."""
    pattern = r'^```(?:java|Java)?\s*\n?(.*?)\n?```\s*$'
    match = re.match(pattern, code.strip(), re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return code.strip()


def generate_llm_tests(java_code: str, coverage_type: str = "branch", class_name: str = None) -> str:
    """Generate JUnit test cases using LLM for the given Java method."""
    try:
        coverage_mapping = {
            "branch": "branch coverage",
            "line": "statement coverage"
        }
        llm_coverage_type = coverage_mapping.get(coverage_type, "branch coverage")
        coverage_guidance = get_coverage_guidance(coverage_type)

        if class_name and class_name.strip():
            class_name = class_name.strip()
            class_name_instruction = f"""The method under test is inside a class named '{class_name}'.
                In your test class, create a private field like this:
                 private final {class_name} anyinstancename (generate suitable instance name) = new {class_name}();
                Then call the method using: anyinstancename (generate suitable instance name).methodName(parameters)
                CRITICAL: You MUST use the class name '{class_name}' EXACTLY as written (including case). Do NOT change the capitalization. Do NOT use any other class name.
                Also name the Test Class as '{class_name}Test'."""
        else:
            class_name_instruction = "Create an instance of the class containing the method and call it, OR call the method directly if it's static"

        result = chain.invoke({
            "coverage_type": llm_coverage_type,
            "method_under_test": java_code,
            "class_name_instruction": class_name_instruction,
            "coverage_guidance": coverage_guidance
        })

        if hasattr(result, 'content'):
            generated_code = result.content
        else:
            generated_code = str(result)
        
        generated_code = strip_markdown_code_blocks(generated_code)
        return generated_code

    except Exception as e:
        return f"Error generating tests with LLM: {str(e)}"


# =============================================================================
# PART 2: MAVEN TEST EXECUTION & COVERAGE COLLECTION
# =============================================================================

class JavaTestPipeline:
    """Pipeline for testing Java methods with JUnit and extracting Jacoco coverage."""
    
    def __init__(self, project_root="test_project", maven_home=None):
        self.project_root = Path(project_root)
        self.maven_home = maven_home
        self.src_main = self.project_root / "src" / "main" / "java"
        self.src_test = self.project_root / "src" / "test" / "java"
        self.maven_cmd = self._setup_maven_command(maven_home)
    
    def _setup_maven_command(self, maven_home):
        """Setup the Maven command based on OS and Maven installation."""
        import platform
        
        if maven_home:
            maven_home = Path(maven_home)
            if platform.system() == "Windows":
                mvn_path = maven_home / "bin" / "mvn.cmd"
            else:
                mvn_path = maven_home / "bin" / "mvn"
            
            if mvn_path.exists():
                print(f"Using Maven from: {mvn_path}")
                return str(mvn_path)
        
        if platform.system() == "Windows":
            for cmd in ['mvn.cmd', 'mvn.bat', 'mvn']:
                mvn_path = shutil.which(cmd)
                if mvn_path:
                    print(f"Found Maven: {mvn_path}")
                    return mvn_path
            
            common_paths = [
                r"C:\apache-maven-3.9.9\bin\mvn.cmd",
                r"C:\Program Files\Apache\maven\bin\mvn.cmd",
                r"C:\Program Files\Maven\bin\mvn.cmd",
            ]
            for path in common_paths:
                if Path(path).exists():
                    print(f"Found Maven at: {path}")
                    return path
        else:
            mvn_path = shutil.which('mvn')
            if mvn_path:
                print(f"Found Maven: {mvn_path}")
                return mvn_path
        
        print("⚠️  Warning: Could not find Maven automatically")
        return 'mvn'
    
    def setup_project_structure(self):
        """Create the Maven project directory structure."""
        self.src_main.mkdir(parents=True, exist_ok=True)
        self.src_test.mkdir(parents=True, exist_ok=True)
        self._create_pom_xml()
        print(f"✓ Project structure created at {self.project_root}")
    
    def _create_pom_xml(self):
        """Generate pom.xml with JUnit 5 and Jacoco dependencies."""
        pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.research</groupId>
    <artifactId>test-pipeline</artifactId>
    <version>1.0-SNAPSHOT</version>
    
    <properties>
        <maven.compiler.source>1.8</maven.compiler.source>
        <maven.compiler.target>1.8</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <junit.version>5.9.3</junit.version>
    </properties>
    
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-api</artifactId>
            <version>${junit.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>${junit.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-params</artifactId>
            <version>${junit.version}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>2.22.2</version>
            </plugin>
            
            <plugin>
                <groupId>org.jacoco</groupId>
                <artifactId>jacoco-maven-plugin</artifactId>
                <version>0.8.10</version>
                <executions>
                    <execution>
                        <goals>
                            <goal>prepare-agent</goal>
                        </goals>
                    </execution>
                    <execution>
                        <id>report</id>
                        <phase>test</phase>
                        <goals>
                            <goal>report</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
            
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.8.1</version>
                <configuration>
                    <source>1.8</source>
                    <target>1.8</target>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>"""
        
        pom_path = self.project_root / "pom.xml"
        with open(pom_path, 'w') as f:
            f.write(pom_content)
    
    def write_java_file(self, java_code, target_dir):
        """Write Java code to appropriate file based on class name."""
        java_code = strip_markdown_code_blocks(java_code)
        
        class_name = extract_class_name(java_code)
        if not class_name:
            print("  ⚠️  Could not extract class name from code")
            return None
        
        file_path = target_dir / f"{class_name}.java"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(java_code)
        
        return file_path
    
    def cleanup_java_files(self):
        """Remove all .java files from src directories."""
        for java_file in self.src_main.glob("*.java"):
            java_file.unlink()
        for java_file in self.src_test.glob("*.java"):
            java_file.unlink()
    
    def run_test_and_coverage(self, test_name):
        """Execute Maven test and generate Jacoco coverage report."""
        try:
            print(f"  Running test: {test_name}")
            result = subprocess.run(
                [self.maven_cmd, 'clean', 'test', 'jacoco:report', '-Dmaven.test.failure.ignore=true'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
                shell=False
            )
            
            success = result.returncode == 0
            output = result.stdout + result.stderr
            
            if success:
                print(f"  ✓ Test passed: {test_name}")
            else:
                print(f"  ✗ Test failed: {test_name}")
                error_snippet = output[-500:] if len(output) > 500 else output
                print(f"  Error snippet: ...{error_snippet}")
            
            return success, output
            
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Test timeout: {test_name}")
            return False, "Test execution timeout"
        except Exception as e:
            print(f"  ✗ Error running test: {e}")
            return False, str(e)
    
    def parse_test_counts(self, output):
        """Extract test run/pass/fail counts from Maven Surefire output."""
        counts = {'tests_run': 0, 'tests_passed': 0, 'tests_failed': 0}
        
        # Surefire prints: Tests run: X, Failures: Y, Errors: Z, Skipped: W
        pattern = r'Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)'
        matches = re.findall(pattern, output)
        
        if matches:
            # Take the last match (the summary line)
            run, failures, errors, skipped = [int(x) for x in matches[-1]]
            counts['tests_run'] = run
            counts['tests_failed'] = failures + errors
            counts['tests_passed'] = run - failures - errors - skipped
        
        return counts
    
    def parse_jacoco_report(self):
        """Extract coverage metrics from Jacoco XML report."""
        jacoco_xml = self.project_root / "target" / "site" / "jacoco" / "jacoco.xml"
        
        if not jacoco_xml.exists():
            print("  ⚠️  Jacoco report not found")
            return None
        
        try:
            tree = ET.parse(jacoco_xml)
            root = tree.getroot()
            
            coverage = {}
            desired_metrics = {'BRANCH'}
            
            for counter in root.findall('.//counter'):
                counter_type = counter.get('type')
                
                if counter_type not in desired_metrics:
                    continue
                
                missed = int(counter.get('missed', 0))
                covered = int(counter.get('covered', 0))
                total = missed + covered
                
                if total > 0:
                    percentage = (covered / total) * 100
                    coverage[counter_type.lower()] = {
                        'covered': covered,
                        'missed': missed,
                        'total': total,
                        'percentage': round(percentage, 2)
                    }
            
            return coverage
            
        except Exception as e:
            print(f"  ✗ Error parsing Jacoco report: {e}")
            return None
    
    def determine_failure_reason(self, test_passed, coverage, output):
        """Determine why a test case failed."""
        if test_passed and coverage:
            return None
        
        output_lower = output.lower()
        
        if 'compilation failure' in output_lower or 'cannot find symbol' in output_lower:
            return "Compilation Error"
        
        if 'test failures' in output_lower or 'failures: ' in output_lower:
            if 'assertionerror' in output_lower:
                return "Test Assertion Failed"
            return "Test Failed"
        
        if 'exception' in output_lower and test_passed == False:
            if 'nullpointerexception' in output_lower:
                return "NullPointerException"
            elif 'arithmeticexception' in output_lower:
                return "ArithmeticException"
            return "Runtime Exception"
        
        if 'tests run: 0' in output_lower:
            return "No Tests Executed"
        
        if test_passed and not coverage:
            return "Jacoco Report Not Generated"
        
        if not test_passed:
            return "Unknown Test Failure"
        
        return "Unknown Issue"


# =============================================================================
# PART 3: MAIN PIPELINE - COMBINED WORKFLOW
# =============================================================================

def run_metrics_pipeline(input_csv="Cog_96_12.csv", maven_home=None, enable_wait=False):
    """
    Run the complete metrics pipeline:
    1. Generate JUnit tests for each MUT (Branch coverage)
    2. Run tests and collect branch coverage metrics
    3. Save results to CSV files
    """
    
    print("=" * 70)
    print("METRICS PIPELINE - JUnit Generation + Branch Coverage Analysis")
    print("=" * 70)
    
    # Output files
    output_detailed = "coverage_results.csv"
    output_summary = "coverage_summary.csv"
    
    print(f"Input file: {input_csv}")
    print(f"Output files: {output_detailed}, {output_summary}")
    
    # Check input file exists
    if not os.path.exists(input_csv):
        print(f"Error: Could not find input file '{input_csv}'")
        return
    
    # Read input CSV
    rows = []
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    total_methods = len(rows)
    print(f"Found {total_methods} methods to process.")
    print(f"Will generate {total_methods} tests and run {total_methods} coverage analyses.\n")
    
    # Initialize Maven pipeline
    pipeline = JavaTestPipeline(
        project_root="test_project_metrics",
        maven_home=maven_home
    )
    pipeline.setup_project_structure()
    
    # Process each method
    all_results = []
    
    for i, row in enumerate(rows):
        mut_code = row.get("method", "")
        if not mut_code:
            continue
        
        # Get complexity metrics from input
        cyclomatic = row.get("cyclomatic", "")
        npath = row.get("npath", "")
        cognitive = row.get("cognitive", "")
        
        class_name = extract_class_name(mut_code)
        
        print(f"\n{'='*60}")
        print(f"[{i+1}/{total_methods}] Processing: {class_name}")
        print("=" * 60)
        
        # ==========================================
        # STEP 1: Generate Branch Coverage Test
        # ==========================================
        print("\n  [STEP 1] Generating Branch Coverage test with LLM...")
        if enable_wait:
            wait_time = random.randint(50,200 )  # 2-5 minutes
            print(f"    Waiting {wait_time} seconds ({wait_time//60} min {wait_time%60} sec)...")
            time.sleep(wait_time)
        
        branch_test = generate_llm_tests(mut_code, "branch", class_name)
        print("    ✓ Branch Coverage test generated.")
        
        # ==========================================
        # STEP 2: Run Branch Coverage Test
        # ==========================================
        print("\n  [STEP 2] Running Branch Coverage test...")
        pipeline.cleanup_java_files()
        
        mut_path = pipeline.write_java_file(mut_code, pipeline.src_main)
        if not mut_path:
            print("    ✗ Failed to write ClassUnderTest")
            branch_test_passed = False
            branch_failure_reason = "Failed to write class file"
            branch_coverage = None
        else:
            test_path = pipeline.write_java_file(branch_test, pipeline.src_test)
            if not test_path:
                print("    ✗ Failed to write Branch Coverage test")
                branch_test_passed = False
                branch_failure_reason = "Failed to write test file"
                branch_coverage = None
            else:
                branch_test_passed, branch_output = pipeline.run_test_and_coverage(f"{class_name}_BranchCov")
                branch_coverage = pipeline.parse_jacoco_report()
                branch_failure_reason = pipeline.determine_failure_reason(branch_test_passed, branch_coverage, branch_output)
                test_counts = pipeline.parse_test_counts(branch_output)
                
                if branch_test_passed:
                    print("    ✓ Branch Coverage test passed")
                else:
                    print(f"    ✗ Branch Coverage test failed: {branch_failure_reason}")
        
        # Get test counts (default to 0 if not set)
        if 'test_counts' not in dir():
            test_counts = {'tests_run': 0, 'tests_passed': 0, 'tests_failed': 0}
        
        # Build result row
        result_row = {
            'class_name': class_name,
            'cyclomatic': cyclomatic,
            'npath': npath,
            'cognitive': cognitive,
            'branch_percentage': branch_coverage.get('branch', {}).get('percentage', '') if branch_coverage else '',
            'tests_run': test_counts['tests_run'],
            'tests_passed': test_counts['tests_passed'],
            'tests_failed': test_counts['tests_failed'],
            'branch_test_passed': branch_test_passed,
            'branch_failure_reason': branch_failure_reason if branch_failure_reason else '',
            'branch_covered': branch_coverage.get('branch', {}).get('covered', '') if branch_coverage else '',
            'branch_missed': branch_coverage.get('branch', {}).get('missed', '') if branch_coverage else '',
            'class_under_test': mut_code,
            'test_script_branch': branch_test
        }
        all_results.append(result_row)
    
    # Save detailed results CSV
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(output_detailed, index=False)
    
    # Save summary CSV (includes complexity metrics)
    summary_columns = ['class_under_test', 'test_script_branch', 'cyclomatic', 'npath', 'cognitive', 'branch_percentage', 'tests_run', 'tests_passed', 'tests_failed']
    summary_df = results_df[summary_columns]
    summary_df.to_csv(output_summary, index=False)
    
    # Print summary
    print("\n" + "=" * 70)
    print("PIPELINE RESULTS SUMMARY")
    print("=" * 70)
    
    total = len(all_results)
    branch_passed = sum(1 for r in all_results if r.get('branch_test_passed') == True)
    
    print(f"\nBranch Coverage Tests: {branch_passed}/{total} passed ({(branch_passed/total)*100:.1f}%)")
    
    branch_coverages = [r['branch_percentage'] for r in all_results if r.get('branch_percentage') != '']
    
    if branch_coverages:
        avg_branch = sum(branch_coverages) / len(branch_coverages)
        print(f"Average Branch Coverage: {avg_branch:.2f}%")
    
    print(f"\n✓ Detailed results saved to: {output_detailed}")
    print(f"✓ Summary results saved to: {output_summary}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Default values
    input_file = "Cog_96_12.csv"
    maven_home = r"C:\apache-maven-3.9.9"  # Update this to your Maven path
    enable_wait = True # Enabled: 5-7 minute wait between LLM calls
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        maven_home = sys.argv[2]
    if len(sys.argv) > 3 and sys.argv[3].lower() == "wait":
        enable_wait = True
        
    # Run the pipeline
    run_metrics_pipeline(
        input_csv=input_file,
        maven_home=maven_home,
        enable_wait=enable_wait
    )
