#!/usr/bin/env python3
"""
End-to-end test for AnywhereCode.

Tests the complete workflow: Plan → Approval → Generation → Git
"""

import json
import tempfile
from pathlib import Path
from typing import Optional

from anyplace.core.mock_llm import MockLLMProvider
from anyplace.core.plan_generator import PlanGenerator
from anyplace.core.build_orchestrator import BuildOrchestrator
from anyplace.cli.progress import GenerationProgress
from anyplace.cli.error_handler import GenerationError, APIError
from anyplace.core.commit_generator import CommitGenerator
from anyplace.core.build_runner import BuildRunner
from anyplace.core.hooks_injector import HooksInjector
from anyplace.core.deploy_generator import DeployGenerator


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


def test_commit_generator():
    """Test commit message generation from a git diff."""
    print("\n" + "=" * 70)
    print("TEST 5: Commit Message Generator")
    print("=" * 70)

    fixture_diff = """diff --git a/src/App.tsx b/src/App.tsx
index abc123..def456 100644
--- a/src/App.tsx
+++ b/src/App.tsx
@@ -1,5 +1,10 @@
+import { useState } from 'react'
 function App() {
-  return <div>Hello</div>
+  const [dark, setDark] = useState(false)
+  return <div className={dark ? 'dark' : ''}>Hello</div>
 }"""

    try:
        mock_llm = MockLLMProvider()
        commit_gen = CommitGenerator(mock_llm)

        message = commit_gen.generate_message(fixture_diff)

        assert message, "Commit message should not be empty"
        assert ":" in message, f"Expected conventional commit format with ':', got: {message!r}"

        print(f"✅ Commit message generated")
        print(f"   Message: {message.splitlines()[0]}")
        return True

    except Exception as e:
        print(f"❌ Commit generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_build_runner_detection():
    """Test project type detection from package.json."""
    print("\n" + "=" * 70)
    print("TEST 6: Build Runner Detection")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Test Expo detection
            expo_dir = Path(tmpdir) / "expo-project"
            expo_dir.mkdir()
            (expo_dir / "package.json").write_text(
                json.dumps({"dependencies": {"expo": "^50.0.0", "react": "^18.0.0"}})
            )
            runner = BuildRunner(expo_dir)
            detected = runner._detect_project_type()
            assert detected == "expo-rn", f"Expected 'expo-rn', got '{detected}'"
            print(f"✅ Expo project detected: {detected}")

            # Test Vite/React detection
            vite_dir = Path(tmpdir) / "vite-project"
            vite_dir.mkdir()
            (vite_dir / "package.json").write_text(
                json.dumps({"devDependencies": {"vite": "^5.0.0"}})
            )
            runner2 = BuildRunner(vite_dir)
            detected2 = runner2._detect_project_type()
            assert detected2 == "react-vite", f"Expected 'react-vite', got '{detected2}'"
            print(f"✅ React/Vite project detected: {detected2}")

            # Test Node.js detection
            node_dir = Path(tmpdir) / "node-project"
            node_dir.mkdir()
            (node_dir / "package.json").write_text(
                json.dumps({"dependencies": {"express": "^4.0.0"}})
            )
            runner3 = BuildRunner(node_dir)
            detected3 = runner3._detect_project_type()
            assert detected3 == "nodejs", f"Expected 'nodejs', got '{detected3}'"
            print(f"✅ Node.js project detected: {detected3}")

            return True

        except Exception as e:
            print(f"❌ Build runner detection failed: {e}")
            return False


def test_hooks_injector():
    """Test Claude Code hooks injection into a project directory."""
    print("\n" + "=" * 70)
    print("TEST 7: Hooks Injector")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()

            injector = HooksInjector(project_dir)
            result = injector.inject(project_type="react-vite")

            settings_path = project_dir / ".claude" / "settings.json"
            assert settings_path.exists(), ".claude/settings.json not created"

            settings = json.loads(settings_path.read_text())
            assert "hooks" in settings, "settings.json missing 'hooks' key"
            assert "PostToolUse" in settings["hooks"], "Missing PostToolUse hook"
            assert "PostSaveFiles" in settings["hooks"], "Missing PostSaveFiles hook"
            print("✅ .claude/settings.json created with hooks")

            build_cmd = project_dir / ".claude" / "commands" / "build.md"
            assert build_cmd.exists(), ".claude/commands/build.md not created"
            print("✅ .claude/commands/ created with slash commands")

            commands_dir = project_dir / ".claude" / "commands"
            cmd_files = list(commands_dir.glob("*.md"))
            print(f"   Commands: {[f.name for f in cmd_files]}")

            return True

        except Exception as e:
            print(f"❌ Hooks injector test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_deploy_generator_eas():
    """Test EAS config generation for Expo projects."""
    print("\n" + "=" * 70)
    print("TEST 8: Deploy Generator (EAS)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            project_dir = Path(tmpdir) / "expo-app"
            project_dir.mkdir()
            (project_dir / "package.json").write_text(
                json.dumps({"dependencies": {"expo": "^50.0.0"}})
            )

            mock_llm = MockLLMProvider()
            deploy_gen = DeployGenerator(project_dir, mock_llm)
            result = deploy_gen.deploy("eas")

            eas_path = project_dir / "eas.json"
            assert eas_path.exists(), "eas.json was not created"

            eas_config = json.loads(eas_path.read_text())
            assert "build" in eas_config, "eas.json missing 'build' key"
            assert "production" in eas_config["build"], "eas.json missing 'production' build profile"

            assert len(result["files_written"]) > 0, "No files listed in result"
            assert len(result["next_steps"]) > 0, "No next steps in result"
            print(f"✅ eas.json generated with build profiles: {list(eas_config['build'].keys())}")
            print(f"   Next steps: {len(result['next_steps'])}")
            return True

        except Exception as e:
            print(f"❌ Deploy generator test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_build_orchestrator_injects_hooks():
    """Test that BuildOrchestrator injects Claude Code hooks after project generation."""
    print("\n" + "=" * 70)
    print("TEST 9: BuildOrchestrator Injects Claude Hooks")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            from anyplace.core.plan_generator import ProjectPlan, FileInfo

            files = [
                FileInfo(
                    path="package.json",
                    description="Project dependencies",
                    file_type="config",
                    dependencies=[],
                ),
                FileInfo(
                    path="README.md",
                    description="Documentation",
                    file_type="doc",
                    dependencies=[],
                ),
            ]

            plan = ProjectPlan(
                project_name="hooks-test",
                template="web-react-vite",
                description="Test hook injection",
                tech_stack=["React", "Vite"],
                files=files,
                key_features=["Hooks test"],
                estimated_time="1 min",
                architecture_notes="Minimal test project",
                next_steps=["Run npm install"],
            )

            mock_llm = MockLLMProvider()
            orchestrator = BuildOrchestrator(
                plan=plan,
                llm_provider=mock_llm,
                project_dir=Path(tmpdir) / "hooks-test",
                use_git=False,
            )

            success = orchestrator.build()
            assert success, "Build returned False"

            project_dir = Path(tmpdir) / "hooks-test"
            settings_path = project_dir / ".claude" / "settings.json"
            assert settings_path.exists(), ".claude/settings.json not found after build"

            settings = json.loads(settings_path.read_text())
            assert "hooks" in settings, "settings.json missing hooks"
            print("✅ Claude hooks injected automatically after build")
            return True

        except Exception as e:
            print(f"❌ Hook injection test failed: {e}")
            import traceback
            traceback.print_exc()
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
        "commit_generator": test_commit_generator(),
        "build_runner_detection": test_build_runner_detection(),
        "hooks_injector": test_hooks_injector(),
        "deploy_generator_eas": test_deploy_generator_eas(),
        "orchestrator_hooks": test_build_orchestrator_injects_hooks(),
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
        ("Commit Generator", results.get("commit_generator", False)),
        ("Build Runner Detection", results.get("build_runner_detection", False)),
        ("Hooks Injector", results.get("hooks_injector", False)),
        ("Deploy Generator (EAS)", results.get("deploy_generator_eas", False)),
        ("Orchestrator Injects Hooks", results.get("orchestrator_hooks", False)),
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
    print("ANYWHEREPLACE END-TO-END TEST SUITE")
    print("🚀 " * 20)

    results = run_full_workflow()
    success = print_summary(results)

    exit(0 if success else 1)
