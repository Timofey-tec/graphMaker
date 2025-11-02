import sys
import os
import tomllib  

CONFIG_PATH = "config.toml"


def load_config(path):
    """Загрузка конфигурационного файла TOML"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл '{path}' не найден.")
    with open(path, "rb") as f:
        try:
            return tomllib.load(f)
        except Exception as e:
            raise ValueError(f"Ошибка чтения TOML: {e}")


def validate_config(cfg):
    """Проверка структуры и типов конфигурации"""
    required_keys = [
        "package_name",
        "repo_path",
        "repo_mode",
        "output_file",
        "ascii_mode",
        "max_depth",
        "filter_substring",
    ]

    for key in required_keys:
        if key not in cfg:
            raise KeyError(f"Отсутствует обязательный параметр: {key}")

    if cfg["repo_mode"] not in ["local", "remote"]:
        raise ValueError("repo_mode должен быть 'local' или 'remote'.")

    if not isinstance(cfg["max_depth"], int):
        raise TypeError("max_depth должен быть числом (int).")

    if not isinstance(cfg["ascii_mode"], bool):
        raise TypeError("ascii_mode должен быть логическим значением (true/false).")

    return True


def main():
    try:
        config = load_config(CONFIG_PATH)
        validate_config(config)
        print("Загруженные параметры конфигурации:\n")
        for k, v in config.items():
            print(f"{k} = {v}")

    except Exception as e:
        print(f"\nОшибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
