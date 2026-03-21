# Инструкция По Работе Со Шлюзом OВЕН RS-485 -> Modbus-TCP

## Назначение

Шлюз опрашивает приборы ОВЕН по `RS-485` с протоколом ОВЕН и публикует данные в `Modbus-TCP`.

Текущая реализация ориентирована на приборы типа `ТРМ138`, где основной рабочий параметр для чтения - `rEAd`.

## Что есть в проекте

- исполняемый модуль: [owen_gateway](/home/r0ahj/PyCharmMiscProject/owen_gateway)
- пример для Windows: [owen_config.windows.json](/home/r0ahj/PyCharmMiscProject/owen_config.windows.json)
- пример для Linux: [owen_config.linux.json](/home/r0ahj/PyCharmMiscProject/owen_config.linux.json)
- карта на 2 шины / 16 приборов: [MODBUS_MAP_2BUS_16DEV.md](/home/r0ahj/PyCharmMiscProject/MODBUS_MAP_2BUS_16DEV.md)

## Требования

- Python `3.12`
- доступ к `RS-485` адаптеру
- корректные настройки линии: для вашего случая `9600 8N1`
- настроенные базовые адреса приборов ОВЕН

## Установка

### Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Перенос На Другую Машину

Переносить нужно сам проект целиком, кроме локального виртуального окружения `.venv`.

Минимально необходимые файлы и каталоги:

- [owen_gateway](/home/r0ahj/PyCharmMiscProject/owen_gateway)
- [requirements.txt](/home/r0ahj/PyCharmMiscProject/requirements.txt)
- нужный конфиг, например [owen_config.windows.json](/home/r0ahj/PyCharmMiscProject/owen_config.windows.json) или [owen_config.linux.json](/home/r0ahj/PyCharmMiscProject/owen_config.linux.json)
- инструкция и карта регистров при необходимости:
  - [OWEN_GATEWAY_GUIDE_RU.md](/home/r0ahj/PyCharmMiscProject/OWEN_GATEWAY_GUIDE_RU.md)
  - [MODBUS_MAP_2BUS_16DEV.md](/home/r0ahj/PyCharmMiscProject/MODBUS_MAP_2BUS_16DEV.md)

Не нужно переносить:

- `.venv`
- `__pycache__`
- `.idea`

Практически самый простой способ:

1. Скопировать папку проекта на новую машину.
2. Создать на новой машине новое виртуальное окружение.
3. Установить зависимости из `requirements.txt`.
4. Проверить и поправить конфиг под реальные `COM`/`/dev/ttyUSB*`.
5. Запустить шлюз.

### Вариант Через Архив

На исходной машине можно упаковать проект в архив без `.venv`.

На Linux:

```bash
tar --exclude='.venv' --exclude='__pycache__' --exclude='.idea' -czf owen_gateway_project.tar.gz .
```

На Windows проще упаковать папку архиватором, но без каталога `.venv`.

### Вариант Через Git

Если проект лежит в git-репозитории, на новой машине достаточно:

```bash
git clone <repo>
```

после чего создать новое окружение и установить зависимости.

## Быстрый старт на Windows

Для одиночного `ТРМ138` используйте конфиг `owen_config.single_trm138.com6.json`.

Файл [owen_config.windows.json](/home/r0ahj/PyCharmMiscProject/owen_config.windows.json) подготовлен как тестовый пример:

- `bus1 -> COM5`
- `bus2 -> COM6`
- `bus3 -> COM7`
- по одному прибору на каждой шине
- для каждого прибора опрашиваются все `8` каналов

Пример запуска:

```powershell
.venv\Scripts\python -m owen_gateway --config owen_config.single_trm138.com6.json --log-level DEBUG
```

### Полный Порядок Запуска На Новой Windows-Машине

1. Установить Python `3.12`.
2. Скопировать проект в рабочую папку.
3. Открыть `PowerShell` в каталоге проекта.
4. Выполнить:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

5. Проверить конфиг:
   - правильные `COM`-порты
   - скорость `9600`
   - `8N1`
6. Запустить:

```powershell
.venv\Scripts\python -m owen_gateway --config owen_config.single_trm138.com6.json --log-level DEBUG
```

7. Проверить, что:
   - в логах нет ошибок открытия порта
   - растет `HR6`
   - читаются `HR1..HR6`

### Автозапуск На Windows

Для постоянной работы можно запускать шлюз:

- через `Task Scheduler`
- через `nssm` как Windows service

В качестве команды запуска использовать:

```powershell
C:\path\to\project\.venv\Scripts\python.exe -m owen_gateway --config C:\path\to\project\owen_config.windows.json --log-level INFO
```

## Быстрый старт на Linux

Пример запуска:

```bash
.venv/bin/python -m owen_gateway --config owen_config.linux.json --log-level INFO
```

### Полный Порядок Запуска На Новой Linux-Машине

1. Установить Python `3.12`.
2. Скопировать проект в рабочий каталог.
3. Открыть shell в каталоге проекта.
4. Выполнить:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

5. Проверить конфиг:
   - правильный порт `/dev/ttyUSB0` или другой
   - скорость `9600`
   - `8N1`
6. Проверить права доступа к последовательному порту.
   Обычно пользователя нужно добавить в группу `dialout`:

```bash
sudo usermod -a -G dialout $USER
```

После этого обычно требуется перелогиниться.

7. Запустить:

```bash
.venv/bin/python -m owen_gateway --config owen_config.linux.json --log-level INFO
```

8. Проверить `Modbus`-регистры `HR1..HR6` и данные каналов.

### Автозапуск На Linux

Проще всего запускать шлюз через `systemd`.

Пример unit-файла:

```ini
[Unit]
Description=OVEN RS485 to Modbus TCP Gateway
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/owen-gateway
ExecStart=/opt/owen-gateway/.venv/bin/python -m owen_gateway --config /opt/owen-gateway/owen_config.linux.json --log-level INFO
Restart=always
RestartSec=3
User=oven

[Install]
WantedBy=multi-user.target
```

Дальше:

```bash
sudo systemctl daemon-reload
sudo systemctl enable owen-gateway
sudo systemctl start owen-gateway
sudo systemctl status owen-gateway
```

## Структура конфигурации

### Упрощенный режим одного прибора

Если прибор один, можно не использовать массив `buses`.

Минимальный состав:

- `serial`
- `poll_interval_ms`
- `modbus`
- `status`
- `telemetry`
- `health`
- `points`

Поле `serial.address_bits` для `ТРМ138` с базовыми адресами `96..103` должно быть `8`.

Секция `health`:

- `stale_after_cycles` - после скольких одинаковых `time mark` подряд канал считать `stale`
- `fault_after_failures` - после скольких подряд ошибок канал считать в отказе
- `recovery_poll_interval_cycles` - как часто перепроверять канал после перехода в отказ

### Блок `buses`

Описывает шины `RS-485`.

Поля:

- `name` - внутреннее имя шины
- `serial.port` - имя порта, например `COM5` или `/dev/ttyUSB0`
- `serial.baudrate`
- `serial.bytesize`
- `serial.parity`
- `serial.stopbits`
- `serial.timeout_ms`
- `poll_interval_ms` - период опроса этой шины

### Блок `points`

Описывает, что именно читать и куда публиковать в `Modbus`.

Поля:

- `name` - имя точки
- `bus` - имя шины
- `device` - номер прибора на шине
- `address` - сетевой адрес ОВЕН для этой точки
- `parameter` - имя параметра ОВЕН, например `rEAd`
- `protocol_format` - формат ответа, для `ТРМ138` обычно `float32`
- `register_type` - сейчас рекомендуется `holding_register`
- `modbus_address` - адрес регистра `Modbus`
- `modbus_data_type` - тип данных `Modbus`
- `time_mark_address` - адрес регистра для временной метки канала
- `channel_status_address` - адрес регистра для статуса канала

## Служебные регистры Modbus

- `HR1` - статус шлюза
- `HR2` - `last_error_code`
- `HR3` - `success_counter`
- `HR4` - `timeout_counter`
- `HR5` - `protocol_error_counter`
- `HR6` - `poll_cycle_counter`

## Коды статуса

- `1` - связь в норме
- `2` - частичная деградация
- `3` - нет ответа
- `4` - протокольная ошибка

## Коды `last_error_code`

- `0` - ошибок нет
- `1` - timeout
- `2` - в ответе установлен request flag
- `3` - hash параметра не совпал
- `4` - ошибка декодирования
- `5` - внутренняя ошибка или ошибка порта

## Коды статуса канала

- `0` - нет данных / пустой payload / канал отключен
- `1` - канал в норме
- `2` - метка не меняется дольше допустимого окна
- `3` - временные ошибки связи
- `4` - протокольная ошибка
- `5` - отказ, канал опрашивается реже

## Как проверять работу

1. Запустить шлюз с `--log-level DEBUG`.
2. Убедиться, что для нужных `COM`-портов открывается соединение.
3. Проверить диагностические сообщения `diag bus=...`.
4. Считать `HR1..HR6` любым `Modbus-TCP` клиентом.
5. Проверить данные каналов по карте регистров.

## Что смотреть при неисправностях

Если `HR1 = 3`:

- прибор не отвечает
- неверный `COM`-порт
- перепутаны линии `A/B`
- неправильная скорость или четность
- нет общего провода или плохой терминатор

Если `HR1 = 4`:

- ответ есть, но кадр не совпадает с ожидаемым
- неверный адрес
- читается не тот параметр
- повреждение данных на линии

Если растет `HR4`:

- это таймауты обмена

Если растет `HR5`:

- это протокольные ошибки

Если `HR6` растет, а `HR3` не растет:

- сам шлюз работает, но данные не читаются

## Рекомендации по эксплуатации

- для первого запуска держать `diagnostics: true`
- после отладки на Linux можно переключить `diagnostics` в `false`
- придерживаться единой карты регистров
- для нескольких приборов на одной шине заранее разнести блоки `HR`
- не разрешать внешним системам писать в регистры данных, если не будет добавлено управление

## Следующее развитие

В следующей версии логично добавить:

- read-only защиту данных
- управляющие регистры `enable/disable device`
- команду сброса счетчиков
- диагностику по каждому прибору отдельно
