import sys
import os
import tomllib
import tarfile
import urllib.request

CONFIG_PATH = "config.toml"

TEST_REPO = {}


def load_config(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл '{path}' не найден.")
    with open(path, "rb") as f:
        return tomllib.load(f)


def validate_config(cfg):
    errors = []

    if not isinstance(cfg.get("package_name"), str) or not cfg["package_name"]:
        errors.append("Некорректное имя пакета.")

    if cfg.get("repo_mode") not in ("remote", "local", "test"):
        errors.append("repo_mode должен быть 'remote', 'local' или 'test'.")

    if not isinstance(cfg.get("repo_path"), str):
        errors.append("repo_path должен быть строкой.")

    if not isinstance(cfg.get("output_file"), str):
        errors.append("output_file должен быть строкой.")

    if not isinstance(cfg.get("ascii_mode"), bool):
        errors.append("ascii_mode должен быть true/false.")

    if not isinstance(cfg.get("max_depth"), int) or cfg["max_depth"] < 0:
        errors.append("max_depth должен быть целым числом ≥ 0.")

    if not isinstance(cfg.get("filter_substring"), str):
        errors.append("filter_substring должен быть строкой.")

    if errors:
        raise ValueError("\n".join(errors))


def download_apk_index(repo_path, repo_mode):
    if repo_mode == "remote":
        print(f"Загрузка APKINDEX из {repo_path} ...")
        urllib.request.urlretrieve(repo_path, "APKINDEX.tar.gz")
        with tarfile.open("APKINDEX.tar.gz", "r:gz") as tar:
            tar.extract("APKINDEX")
        return "APKINDEX"

    elif repo_mode == "local":
        apk = os.path.join(repo_path, "APKINDEX")
        if not os.path.exists(apk):
            raise FileNotFoundError(f"Не найден локальный файл: {apk}")
        return apk

    else:
        return None


def parse_apk_index(index_path, package_name):
    deps = []
    current = None
    with open(index_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("P:"):
                current = line[2:]
            elif line.startswith("D:") and current == package_name:
                deps = [d for d in line[2:].split(" ") if d]
                break
    return deps




def load_test_repo_graph(path):
    global TEST_REPO
    TEST_REPO = {}

    with open(path, "r") as f:
        for line in f:
            if ":" not in line:
                continue
            pkg, deps = line.strip().split(":")
            deps = deps.strip().split() if deps.strip() else []
            TEST_REPO[pkg.strip()] = deps




def get_all_dependencies_bfs(root, index_path, max_depth, filter_substring, is_test):
    graph = {}
    visited = set()
    queue = [(root, 0)]

    while queue:
        pkg, depth = queue.pop(0)
        if pkg in visited:
            continue
        visited.add(pkg)

        if depth > max_depth:
            continue

        if filter_substring and filter_substring in pkg:
            continue

        if is_test:
            deps = TEST_REPO.get(pkg, [])
        else:
            deps = parse_apk_index(index_path, pkg)

        graph[pkg] = deps

        for d in deps:
            if d not in visited:
                queue.append((d, depth + 1))

    return graph




def build_reverse_graph(graph):
    """Разворачивает граф: A->B -> B->A"""
    rev = {}
    for pkg in graph:
        rev.setdefault(pkg, [])
        for dep in graph[pkg]:
            rev.setdefault(dep, [])
            rev[dep].append(pkg)
    return rev


def get_reverse_dependencies_bfs(target, reverse_graph):
    """BFS по обратному графу"""
    result = set()
    queue = [target]
    visited = set()

    while queue:
        pkg = queue.pop(0)
        if pkg in visited:
            continue
        visited.add(pkg)

        for parent in reverse_graph.get(pkg, []):
            if parent not in result:
                result.add(parent)
                queue.append(parent)

    return result




def main():
    try:
        config = load_config(CONFIG_PATH)
        validate_config(config)

        print("Загруженные параметры:")
        for key, value in config.items():
            print(f"{key} = {value}")
        print()

        is_test = config["repo_mode"] == "test"

        if is_test:
            print("Тестовый режим: загрузка тестового репозитория...")
            load_test_repo_graph(config["repo_path"])
            index_path = None
        else:
            print("Получение APKINDEX...")
            index_path = download_apk_index(config["repo_path"], config["repo_mode"])

        print(f"\nПрямые зависимости '{config['package_name']}':")
        if is_test:
            deps = TEST_REPO.get(config["package_name"], [])
        else:
            deps = parse_apk_index(index_path, config["package_name"])

        for d in deps:
            print(f"  - {d}")

        print("\nПостроение полного графа зависимостей (BFS)...")
        full_graph = get_all_dependencies_bfs(
            config["package_name"],
            index_path,
            config["max_depth"],
            config["filter_substring"],
            is_test
        )

        print("\nПолный граф зависимостей:")
        for pkg, deps in full_graph.items():
            print(f"{pkg}: {', '.join(deps) if deps else '(нет deps)'}")

        print("\n==== ОБРАТНЫЕ ЗАВИСИМОСТИ ====")
        rev = build_reverse_graph(full_graph)
        reverse_deps = get_reverse_dependencies_bfs(config["package_name"], rev)

        if reverse_deps:
            for p in reverse_deps:
                print(f"{p} зависит от {config['package_name']}")
        else:
            print("Нет пакетов, которые зависят от данного.")

    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
