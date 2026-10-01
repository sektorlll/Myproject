[app]
title = Philips Remote
package.name = philipsremote
package.domain = org.mauricio
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3,kivy,requests,urllib3,idna,chardet,certifi
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0
