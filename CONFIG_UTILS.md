# Config Utilities

Утилиты доступны через общий CLI:

```powershell
python -m owen_gateway config ...
```

После `set-line` и `add-trm138` рядом с JSON автоматически создаётся файл:

```text
<config_name>.modbus_map.md
```

Это текстовая карта `Modbus` для текущего конфига.

## Настройка линии

Создать или обновить линию:

```powershell
python -m owen_gateway config set-line `
  --config owen_config.json `
  --line 1 `
  --port COM6 `
  --baudrate 9600 `
  --bytesize 8 `
  --parity N `
  --stopbits 1 `
  --timeout-ms 1000 `
  --address-bits 8 `
  --poll-interval-ms 1000 `
  --slave-base 10
```

Если `--slave-base` не задан, используются значения по умолчанию:

- `line1 -> 10`
- `line2 -> 50`
- `line3 -> 90`
- `line4 -> 130`

## Добавление TRM138

Добавить прибор `TRM138` на выбранную линию:

```powershell
python -m owen_gateway config add-trm138 `
  --config owen_config.json `
  --line 2 `
  --base-address 48 `
  --channels 1-8 `
  --tag trm138_line2_addr48
```

Параметры:

- `--line` номер линии `1..4`
- `--base-address` базовый адрес прибора ОВЕН
- `--channels` список каналов, например `1-8` или `1,2,5`
- `--tag` префикс для имён точек

Что делает команда:

- находит следующий свободный номер прибора на линии
- создаёт точки `rEAd` для выбранных каналов
- назначает карту `HR16..HR47` по схеме `4 регистра на канал`
- сохраняет результат обратно в JSON
- обновляет рядом текстовый файл карты `Modbus`

## Просмотр конфига

Краткая сводка по линиям и приборам:

```powershell
python -m owen_gateway config list-config --config owen_config.json
```

Отдельно можно вывести приборы на линии:

```powershell
python -m owen_gateway config list-line --config owen_config.json --line 1
```

И карточку конкретного прибора:

```powershell
python -m owen_gateway config show-trm138 --config owen_config.json --line 1 --base-address 96
```

Карточка показывает:

- `SlaveID`
- базовый адрес
- служебный тег
- таблицу `канал -> OVEN address -> Modbus registers -> type`

## Экспорт конфига

Сохранить текущий конфиг в отдельный файл:

```powershell
python -m owen_gateway config export-config --config owen_config.json --output owen_config.runtime.json
```

Команда создаёт:

- новый JSON-конфиг
- соседний файл карты `Modbus`

## Удаление прибора

Удалить `TRM138` можно по одному из трёх селекторов:

```powershell
python -m owen_gateway config remove-trm138 --config owen_config.json --line 2 --device 1
python -m owen_gateway config remove-trm138 --config owen_config.json --line 2 --base-address 48
python -m owen_gateway config remove-trm138 --config owen_config.json --line 2 --tag trm138_line2_addr48
```

## Изменение каналов прибора

Можно изменить состав опрашиваемых каналов у уже существующего прибора:

```powershell
python -m owen_gateway config set-trm138-channels --config owen_config.json --line 1 --base-address 96 --channels 1-6,8
```

Поддерживаются те же селекторы:

```powershell
python -m owen_gateway config set-trm138-channels --config owen_config.json --line 1 --device 1 --channels 1-6,8
python -m owen_gateway config set-trm138-channels --config owen_config.json --line 1 --tag trm138_main --channels 1-6,8
```

## Удаление линии

Удаляет саму линию и все привязанные к ней приборы:

```powershell
python -m owen_gateway config remove-line --config owen_config.json --line 2
```

## Меню

Есть интерактивный режим:

```powershell
python -m owen_gateway config menu --config owen_config.json
```

В нём доступны:

- просмотр сводки
- настройка линии
- добавление `TRM138`
- удаление линии
- экспорт текущего конфига в отдельный файл
- пересборка файла карты `Modbus`

Через пункт `Line submenu`:

- выводится список приборов выбранной линии
- показывается карточка выбранного прибора
- меняются каналы прибора
- удаляется прибор
- добавляется новый `TRM138` на эту линию

## Пример

```powershell
python -m owen_gateway config set-line --config owen_config.json --line 1 --port COM6 --baudrate 9600 --parity N --timeout-ms 1000
python -m owen_gateway config add-trm138 --config owen_config.json --line 1 --base-address 96 --channels 1-8 --tag trm138_main
python -m owen_gateway --config owen_config.json
```
