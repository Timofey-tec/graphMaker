import sys
import os
import tomllib
import tarfile
import urllib.request

CONFIG_PATH = "config.toml"

# Глобальное хранилище для тестового режима
TEST_REPO = {}


def load_config(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл '{path}' не найден.")
    with open(path, "rb") as f:
        return tomllib.load(f)


def validate_config(cfg):
    errors = []

    # Имя пакета
    if not isinstance(cfg.get("package_name"), str) or not cfg["package_name"]:
        errors.append("Некорректное имя пакета.")

    # Режим репозитория
    if cfg.get("repo_mode") not in ("remote", "local", "test"):
        errors.append("repo_mode должен быть 'remote', 'local' или 'test'.")

    # Путь или URL
    if not isinstance(cfg.get("repo_path"), str):
        errors.append("repo_path должен быть строкой.")

    # Имя выходного файла
    if not isinstance(cfg.get("output_file"), str):
        errors.append("output_file должен быть строкой.")

    # ASCII-режим
    if not isinstance(cfg.get("ascii_mode"), bool):
        errors.append("ascii_mode должен быть true/false.")

    # Максимальная глубина
    if not isinstance(cfg.get("max_depth"), int) or cfg["max_depth"] < 0:
        errors.append("max_depth должен быть целым числом ≥ 0.")

    # Подстрока-фильтр
    if not isinstance(cfg.get("filter_substring"), str):
        errors.append("filter_substring должен быть строкой.")

    if errors:
        raise ValueError("\n".join(errors))


def download_apk_index(repo_path, repo_mode):
    """Получает APKINDEX: скачивание, локальный путь или test-режим"""
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
        # test mode — APKINDEX не нужен
        return None


def parse_apk_index(index_path, package_name):
    """Возвращает прямые зависимости пакета из APKINDEX."""
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
    """Парсер тестового графа:
       Формат:
           A: B C
           B: C
           C:
    """
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
    """Построение полного графа зависимостей BFS без рекурсии."""
    graph = {}
    visited = set()
    queue = [(root, 0)]

    while queue:
        pkg, depth = queue.pop(0)

        if pkg in visited:
            continue
        visited.add(pkg)

        # Ограничение глубины
        if depth > max_depth:
            continue

        # Фильтр
        if filter_substring and filter_substring in pkg:
            continue

        # Получаем зависимости пакета
        if is_test:
            deps = TEST_REPO.get(pkg, [])
        else:
            deps = parse_apk_index(index_path, pkg)

        graph[pkg] = deps

        # BFS очередь
        for d in deps:
            if d not in visited:
                queue.append((d, depth + 1))

    return graph


def main():
    try:
        config = load_config(CONFIG_PATH)
        validate_config(config)

        print("Загруженные параметры:")
        for key, value in config.items():
            print(f"{key} = {value}")
        print()

        #режим test/local/remote
        is_test = config["repo_mode"] == "test"

        if is_test:
            print("Тестовый режим: загрузка тестового репозитория...")
            load_test_repo_graph(config["repo_path"])
            index_path = None
        else:
            print("Получение APKINDEX...")
            index_path = download_apk_index(config["repo_path"], config["repo_mode"])

        print(f"\nАнализ прямых зависимостей '{config['package_name']}'...")
        if not is_test:
            deps = parse_apk_index(index_path, config["package_name"])
        else:
            deps = TEST_REPO.get(config["package_name"], [])

        if deps:
            print("Прямые зависимости:")
            for d in deps:
                print(f"  - {d}")
        else:
            print("Прямых зависимостей не найдено.")

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
            deps_str = ", ".join(deps) if deps else "(нет deps)"
            print(f"{pkg}: {deps_str}")

    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
