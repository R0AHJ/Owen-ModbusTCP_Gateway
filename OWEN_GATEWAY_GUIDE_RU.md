# Инструкция По Работе Со Шлюзом OVEN RS-485 -> Modbus TCP

## Назначение

Шлюз опрашивает приборы OVEN по `RS-485` только по протоколу OVEN и публикует
данные в `Modbus TCP`.

Текущая реализация ориентирована на `TRM138`.

## Основные Правила

- сервисные теги находятся в `SlaveID 1`
- `SlaveID` прибора равен его базовому адресу OVEN
- карта `TRM138`:
  - значения `HR16..HR31`
  - `time mark` `HR32..HR39`
  - статус каналов `HR40..HR47`
  - маска ЛУ `HR48`
- `time mark` публикуется, но не участвует в расчете статуса канала

## Коды Статуса Канала

- `0` нет данных / пустой payload / канал отключен
- `1` канал в норме
- `2` временная ошибка связи
- `3` протокольная ошибка
- `4` отказ, канал опрашивается реже

## Коды Статуса Шлюза

- `1` связь в норме
- `2` частичная деградация
- `3` нет ответа
- `4` протокольная ошибка

## Коды `last_error_code`

- `0` ошибок нет
- `1` timeout
- `2` bad flag
- `3` hash mismatch
- `4` decode error
- `5` io error

## Параметры TRM138

Поддерживаются:

- `rEAd`
- `C.SP`
- `HYSt`
- `AL.t`

Особенности:

- `C.SP`, `HYSt`, `AL.t` читаются по адресу канала, как `rEAd`
- `C.SP` декодируется из формата OVEN `stored_dot`
- поддержаны `2`-байтные и `3`-байтные ответы `stored_dot`

Проверенные примеры декодирования:

- `00 4b` -> `75.0`
- `13 e8` -> `100.0`
- `2b c2` -> `30.1`
- `20 24 ea` -> `94.5`

## Маска Логических Устройств

В `HR48` публикуется одна маска состояний ЛУ:

- `bit0 -> LU1`
- `bit1 -> LU2`
- `...`
- `bit7 -> LU8`

Расчет идет по:

- текущему `rEAd`
- `C.SP`
- `HYSt`
- `AL.t`

Поддержанные режимы `AL.t`:

- `1` прямой гистерезис
- `2` обратный гистерезис
- `3` внутри полосы
- `4` вне полосы

## Конфигурация

Секция `health`:

- `fault_after_failures`
- `recovery_poll_interval_cycles`

Старое поле `stale_after_cycles` можно оставлять в старых JSON, но оно
игнорируется.

Готовые примеры:

- [owen_config.single_trm138.com6.json](/D:/Python_Project/owen_config.single_trm138.com6.json)
- [owen_config.com6.two_trm138.addr48_96.json](/D:/Python_Project/owen_config.com6.two_trm138.addr48_96.json)
- [owen_config.linux.json](/D:/Python_Project/owen_config.linux.json)
- [owen_config.windows.json](/D:/Python_Project/owen_config.windows.json)

## Установка

Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Запуск

```bash
python -m owen_gateway --config owen_config.json
```

Проверка одного прибора:

```bash
python -m owen_gateway.probe --config owen_probe.com6.json --log-level INFO
```

## Проверка Работы

1. Запустить шлюз.
2. Проверить `HR1..HR6` в `SlaveID 1`.
3. Проверить значения каналов в `SlaveID` прибора.
4. Проверить `HR48`, если используются `C.SP`, `HYSt`, `AL.t`.

## Linux

Для Linux подготовлен шаблон [owen_config.linux.json](/D:/Python_Project/owen_config.linux.json).

Типовой запуск:

```bash
.venv/bin/python -m owen_gateway --config owen_config.linux.json --log-level INFO
```

Для постоянной работы удобнее использовать `systemd`.
