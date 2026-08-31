# Назначение файлов проекта

## Корень

- `README.md` — точка входа: правила миграции, команды установки, dry-run, live-запуска и rollback.
- `pyproject.toml` — метаданные Python-пакета, консольная команда `rkn010-migrate` и настройки pytest.
- `requirements.txt` — диапазоны библиотек для Excel, HTTP и тестов.
- `.gitignore` — исключает токены, cookie, боевые Excel-файлы, локальные зависимости и результаты запусков.
- `auth/README.md` — правила подготовки Cookie/JWT/CA для каждого контура.
- `auth/dev`, `auth/psi`, `auth/prod`, `auth/custom` — отслеживаемый каркас профилей; рабочие секреты внутри остаются локальными.
- `input/README.md` — правила размещения локальных Excel-файлов.
- `input/dev`, `input/psi`, `input/prod`, `input/custom` — раздельные локальные каталоги исходных файлов по контурам.

## Пакет `rkn010_migration`

- `__init__.py` — версия пакета.
- `__main__.py` — запуск командой `python -m rkn010_migration`.
- `cli.py` — команды `validate`, `run`, `auth`, `rollback`; защита PROD и каталог запуска.
- `profiles.py` — адреса `dev`, `psi`, `prod` и пользовательский стенд через `--base-url`.
- `config.py` — коллекции, карточка Роскомнадзора, тип реестра и выключенный флаг сроков действия.
- `models.py` — модели строки Excel, замечания, плана лицензии и результата чтения книги.
- `excel_input.py` — поиск заголовков, чтение идентификаторов, разбор дат и валидация таблицы.
- `planner.py` — группировка по ОГРН и зоне, сортировка истории, статус лицензии.
- `subject.py` — построение субъекта из `organizations`, очистка и проверка обязательного минимума.
- `mapping.py` — формирование `forRegistry`, лицензии и реестровой записи RKN010.
- `api.py` — HTTP-клиент: авторизация, повторы, поиск, создание, изменение и удаление.
- `migrator.py` — идемпотентный алгоритм, безопасная смена `active/reissued`, компенсация и проверка.
- `state.py` — атомарный checkpoint и rollback созданий/изменений.
- `runlog.py` — обычный лог и машинный JSONL-журнал.

## Скрипты

- `scripts/bootstrap.ps1` — создаёт `.venv`, локальные файлы авторизации и каталоги входных файлов, ставит зависимости и запускает тесты.
- `scripts/auth.ps1` — общая проверка Cookie/JWT выбранного профиля.
- `scripts/auth-dev.ps1`, `auth-psi.ps1`, `auth-prod.ps1`, `auth-custom.ps1` — короткие проверки авторизации штатных и дополнительного стендов.
- `scripts/run.ps1` — общий запуск для штатного или пользовательского профиля.
- `scripts/run-dev.ps1`, `run-psi.ps1`, `run-prod.ps1` — короткие команды для каждого стенда.
- `scripts/run-custom.ps1` — запуск дополнительного стенда с явным `-BaseUrl`.
- `scripts/rollback.ps1` — общий предварительный или фактический откат по checkpoint.
- `scripts/rollback-dev.ps1`, `rollback-psi.ps1`, `rollback-prod.ps1`, `rollback-custom.ps1` — профильные обёртки отката.

## Тесты

- `tests/conftest.py` — фабрика строк и эталонный субъект.
- `tests/test_excel_input.py` — заголовки Excel, ведущие нули, запрет составной зоны.
- `tests/test_mapping.py` — даты, N1/N2/N3, повторы ESNSI, аннулирование.
- `tests/test_planner.py` — группировка, порядок истории и статус.
- `tests/test_subject.py` — форматы ответа `organizations` и проверка субъекта.
- `tests/test_migrator.py` — полный fake API, безопасный порядок и идемпотентный повтор.
- `tests/test_state.py` — порядок rollback.
