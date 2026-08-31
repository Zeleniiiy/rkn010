# Миграция RKN010

Инструмент переносит лицензии и реестровые записи операторов связи из Excel в коллекции ПГС:

- `RKN010_Licenses` — одна лицензия на сочетание «ОГРН + зона нумерации»;
- `RKN010_Records` — история реестровых записей этой лицензии;
- `organizations` — источник карточки организации/субъекта по ОГРН.

По умолчанию запуск безопасный: он только валидирует таблицу и формирует dry-run payload’ы. Запись в API начинается исключительно с флагом `--execute`. Для `prod` дополнительно обязателен `--confirm-prod`.

## Реализованные правила

- номер лицензии равен зоне нумерации;
- субъект лицензии и всех её записей одинаков;
- значения N1/N2/N3 сохраняются раздельно;
- `licenceNumberESNSI` собирается через пробел без удаления повторов;
- история внутри лицензии сортируется по числовому регистрационному номеру;
- последняя реестровая запись всегда имеет статус `active`;
- предыдущие записи имеют статус `reissued`;
- приказ об исключении переводит лицензию в `annulled`, но последняя реестровая запись остаётся `active`;
- новая `active`-запись создаётся до перевода старой в `reissued`;
- файлы в v1 не загружаются, но существующие файловые метаданные при обновлении не стираются;
- сроки действия пока не отправляются; точка расширения оставлена в `mapping.py`.

## Быстрый старт

```powershell
.\scripts\bootstrap.ps1
```

Положите авторизационные данные в игнорируемые Git файлы:

```text
auth/psi/token.md
auth/psi/cookie.md
auth/dev/token.md
auth/dev/cookie.md
auth/prod/token.md
auth/prod/cookie.md
auth/custom/token.md
auth/custom/cookie.md
```

Каталоги `auth/dev`, `auth/psi`, `auth/prod`, `auth/custom` и аналогичные
каталоги `input/<profile>` входят в репозиторий как безопасный каркас.
`scripts/bootstrap.ps1` создаёт отсутствующие локальные `token.md` и
`cookie.md`, не перезаписывая уже заполненные файлы. В Git сохраняются только
`.gitkeep`, примеры и пояснения — реальные Cookie, JWT, CA-цепочки и Excel-файлы
игнорируются.

Рабочую книгу можно хранить в `input/dev`, `input/psi`, `input/prod` или
`input/custom`; в команду запуска всё равно передаётся её полный путь.

Проверка авторизации отдельными командами:

```powershell
.\scripts\auth-dev.ps1
.\scripts\auth-psi.ps1
.\scripts\auth-prod.ps1
```

Если стенд использует ведомственный центр сертификации, положите его цепочку
в PEM-формате в `auth/<profile>/ca.pem` или передайте путь через
`--ca-bundle C:\\path\\ca.pem`. Отключение проверки TLS не рекомендуется.

Сначала проверьте таблицу:

```powershell
.venv\Scripts\python.exe -m rkn010_migration validate --workbook "C:\path\migration.xlsx"
```

Dry-run для PSI:

```powershell
.\scripts\run-psi.ps1 -Workbook "C:\path\migration.xlsx"
```

Ограниченный тест записи на PSI:

```powershell
.\scripts\run-psi.ps1 -Workbook "C:\path\migration.xlsx" -Execute -Limit 1 -OperatorMode
```

Полная запись на PSI:

```powershell
.\scripts\run-psi.ps1 -Workbook "C:\path\migration.xlsx" -Execute -OperatorMode
```

Обёртки `run-dev.ps1`, `run-psi.ps1` и `run-prod.ps1` используют раздельные
профили и авторизационные файлы. Для дополнительного контура:

```powershell
.\scripts\run-custom.ps1 -BaseUrl "https://api.example" -Workbook "C:\path\migration.xlsx"
```

По умолчанию эта команда использует `auth/custom`. Если задать другое имя
через `-Profile`, нужно создать совпадающий каталог `auth/<profile>`.

Запись на PROD требует отдельного подтверждения:

```powershell
.\scripts\run-prod.ps1 -Workbook "C:\path\migration.xlsx" -Execute -ConfirmProd -OperatorMode
```

## Возобновление и откат

Каждый запуск привязан к профилю и SHA-256 исходного файла. В `runs/<profile>/...` сохраняются:

- `plan.json` — разобранный бизнес-план;
- `payloads.jsonl` — payload’ы dry-run;
- `checkpoint.json` — созданные/изменённые ID и прогресс;
- `events.jsonl` — машинный журнал операций;
- `migration.log` — читаемый лог;
- `summary.json` — итог live-запуска.

Повторный запуск того же файла продолжает checkpoint и пропускает завершённые группы. Предварительный просмотр отката:

```powershell
.venv\Scripts\python.exe -m rkn010_migration rollback --profile psi --state "runs\psi\...\checkpoint.json"
```

Фактический откат:

```powershell
.venv\Scripts\python.exe -m rkn010_migration rollback --profile psi --state "runs\psi\...\checkpoint.json" --execute
```

То же через профильные PowerShell-обёртки:

```powershell
.\scripts\rollback-dev.ps1 -State "C:\path\checkpoint.json"
.\scripts\rollback-psi.ps1 -State "C:\path\checkpoint.json" -Execute
.\scripts\rollback-prod.ps1 -State "C:\path\checkpoint.json" -Execute -ConfirmProd
```

Подробности: [описание файлов](docs/FILES.md), [маппинг](docs/MAPPING.md), [регламент запуска](docs/OPERATIONS.md), [открытые решения](docs/OPEN_QUESTIONS.md).
