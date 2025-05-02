# Ubibot integration for Home Assistant

This repo provides a plugin to work with Ubibot thermometers as sensors

## Installation

Install using HACS

## Configuration

Configure as a sensor in HA YAML configuration

```
sensor:
  - platform: ubibot
    account_key: YOUR_ACCOUNT_KEY_HERE
    channel: YOUR_CHANNEL_ID_HERE
    scan_interval: 900   # optional, in seconds
```
