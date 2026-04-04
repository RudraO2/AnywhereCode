#!/usr/bin/env python3
"""
End-to-end test for AnywhereCode.

Tests the complete workflow: Plan → Approval → Generation → Git
"""

import tempfile
from pathlib import Path
from typing import Optional

from anyplace.core.mock_llm import MockLLMProvider
from anyplace.core.plan_generator import PlanGenerator
from anyplace.core.build_orchestrator import BuildOrchestrator
from anyplace.cli.progress import GenerationProgress
from anyplace.cli.error_handler import GenerationError, APIError


def test_plan_generation():
    """Test plan generation phase."""
    print("\n" + "=" * 70)
    print("TEST 1: Plan Generation")
    print("=" * 70)

    try:
        mock_llm = MockLLMProvider()

        # Simulate what PlanGenerator would do
        plan_data = mock_llm.generate_json("Generate a plan")

        print(f"✅ Plan Generated")
        print(f"   Project: {plan_data['project_name']}")
        print(f"   Template: {plan_data['template']}")
        print(f"   Files: {len(plan_data['files'])}")
        print(f"   Tech Stack: {', '.join(plan_data['tech_stack'])}")

        return plan_data

    except Exception as e:
        print(f"❌ Plan generation failed: {e}")
        return None


def test_code_generation(plan_data: dict) -> bool:
    """Test code generation phase."""
    print("\n" + "=" * 70)
    print("TEST 2: Code Generation with Progress")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Create plan object
            from anyplace.core.plan_generator import ProjectPlan, FileInfo

            files = [
                FileInfo(
                    path=f['path'],
                    description=f['description'],
                    file_type=f['file_type'],
                    dependencies=f['dependencies'],
                )
                for f in plan_data['files']
            ]

            plan = ProjectPlan(
                project_name=plan_data['project_name'],
                template=plan_data['template'],
                description=plan_data['description'],
                tech_stack=plan_data['tech_stack'],
                files=files,
                key_features=plan_data['key_features'],
                estimated_time=plan_data['estimated_time'],
                architecture_notes=plan_data['architecture_notes'],
                next_steps=plan_data['next_steps'],
            )

            # Initialize orchestrator
            mock_llm = MockLLMProvider()
            orchestrator = BuildOrchestrator(
                plan=plan,
                llm_provider=mock_llm,
                project_dir=Path(tmpdir) / "test-project",
                use_git=True,
            )

            # Show progress
            progress = GenerationProgress(len(plan.files), plan.project_name)
            progress.show_generation_start()

            # Generate
            success = orchestrator.build(
                progress_callback=progress.show_file_progress
            )

            if success:
                project_info = orchestrator.get_project_info()
                print()
                progress.show_generation_complete(project_info["project_dir"])
                print(f"\n✅ Code Generation Successful")
                print(f"   Files: {project_info['files_generated']}/{project_info['total_files']}")
                print(f"   Git: {'enabled' if project_info['git_enabled'] else 'disabled'}")

                # List generated files
                project_path = Path(project_info["project_dir"])
                if project_path.exists():
                    generated_files = []
                    for file_path in project_path.rglob("*"):
                        if file_path.is_file() and not str(file_path).startswith("."):
                            rel_path = file_path.relative_to(project_path)
                            generated_files.append(str(rel_path))

                    print(f"\n📁 Generated Files ({len(generated_files)}):")
                    for f in sorted(generated_files):
                        if not f.startswith("."):
                            print(f"   ✅ {f}")

                return True
            else:
                print("❌ Generation returned false")
                return False

        except (GenerationError, APIError) as e:
            print(f"❌ Generation error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_plan_approval():
    """Test plan approval workflow."""
    print("\n" + "=" * 70)
    print("TEST 3: Plan Preview & Approval")
    print("=" * 70)

    try:
        from anyplace.core.plan_generator import ProjectPlan, FileInfo
        from anyplace.cli.plan_preview import display_plan_summary, display_file_plan

        files = [
            FileInfo(
                path="src/main.tsx",
                description="Application entry point",
                file_type="source",
                dependencies=[]
            ),
            FileInfo(
                path="src/App.tsx",
                description="Root React component",
                file_type="source",
                dependencies=["src/main.tsx"]
            ),
            FileInfo(
                path="package.json",
                description="Project dependencies",
                file_type="config",
                dependencies=[]
            ),
        ]

        plan = ProjectPlan(
            project_name="test-app",
            template="web-react-vite",
            description="A test React application",
            tech_stack=["React", "Vite", "TypeScript"],
            files=files,
            key_features=["Component-based", "Fast builds"],
            estimated_time="10 minutes",
            architecture_notes="Modern React with Vite tooling",
            next_steps=["npm install", "npm run dev"],
        )

        print("\n📋 Plan Preview:")
        display_plan_summary(plan)
        display_file_plan(plan)

        print("\n✅ Plan Display Working")
        return True

    except Exception as e:
        print(f"❌ Plan preview failed: {e}")
        return False


def test_git_integration():
    """Test git integration."""
    print("\n" + "=" * 70)
    print("TEST 4: Git Integration")
    print("=" * 70)

    from anyplace.core.git_manager import GitManager

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            repo_path = Path(tmpdir) / "test-repo"
            repo_path.mkdir()  # Create directory first

            git = GitManager(repo_path)

            # Check git installed
            if git.check_git_installed():
                print("✅ Git is installed")
            else:
                print("❌ Git not available")
                return False

            # Initialize repo
            git.init_repo()
            print("✅ Repository initialized")

            # Create .gitignore
            git.create_gitignore()
            gitignore = repo_path / ".gitignore"
            if gitignore.exists():
                print("✅ .gitignore created")
            else:
                print("❌ .gitignore not created")
                return False

            # Create test file
            test_file = repo_path / "test.txt"
            test_file.write_text("Test content")

            # Commit
            git.add_and_commit("test.txt", "Initial commit")
            print("✅ File committed")

            return True

        except Exception as e:
            print(f"❌ Git test failed: {e}")
            return False


def run_full_workflow():
    """Run complete end-to-end workflow."""
    print("\n" + "=" * 70)
    print("FULL WORKFLOW TEST")
    print("=" * 70)

    results = {
        "plan_generation": test_plan_generation(),
        "plan_approval": test_plan_approval(),
        "git_integration": test_git_integration(),
    }

    # Generate code with the plan
    if results["plan_generation"]:
        results["code_generation"] = test_code_generation(results["plan_generation"])

    return results


def print_summary(results: dict):
    """Print test summary."""
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    tests = [
        ("Plan Generation", results.get("plan_generation") is not None),
        ("Plan Approval", results.get("plan_approval", False)),
        ("Code Generation", results.get("code_generation", False)),
        ("Git Integration", results.get("git_integration", False)),
    ]

    passed = 0
    failed = 0

    for test_name, status in tests:
        emoji = "✅" if status else "❌"
        status_text = "PASS" if status else "FAIL"
        print(f"{emoji} {test_name}: {status_text}")
        if status:
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")
    print("=" * 70)

    return passed == len(tests)


if __name__ == "__main__":
    print("\n" + "🚀 " * 20)
    print("ANYWHERECOMDE END-TO-END TEST SUITE")
    print("🚀 " * 20)

    results = run_full_workflow()
    success = print_summary(results)

    exit(0 if success else 1)
