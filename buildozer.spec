[app]
title = VerseLens
package.name = app
package.domain = com.verselens
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,qml,js,db
source.exclude_dirs = VerseLens.AppDir, tools, deployment, bin, .venv, .buildozer, __pycache__
source.exclude_patterns = VerseLens.png, *.AppImage, *.apk
version = 0.1.0
android.release_artifact = apk
requirements = python3==3.11.16,hostpython3==3.11.16,shiboken6,PySide6
orientation = portrait
osx.python_version = 3
osx.kivy_version = 1.9.1
fullscreen = 0
android.archs = arm64-v8a
android.allow_backup = True
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.10.0
ios.codesign.allowed = false
android.ndk_path = /home/gwhitlock/.pyside6_android_deploy/android-ndk/android-ndk-r27c
android.sdk_path = /home/gwhitlock/.pyside6_android_deploy/android-sdk
p4a.bootstrap = qt
p4a.local_recipes = /home/gwhitlock/Desktop/workspace/VerseLens/deployment/recipes
p4a.branch = develop
android.permissions = android.permission.INTERNET, android.permission.WRITE_EXTERNAL_STORAGE
android.add_jars = /home/gwhitlock/Desktop/workspace/VerseLens/deployment/jar/PySide6/jar/Qt6Android.jar,/home/gwhitlock/Desktop/workspace/VerseLens/deployment/jar/PySide6/jar/Qt6AndroidBindings.jar
p4a.extra_args = --qt-libs=Widgets,Gui,Core --load-local-libs=plugins_platforms_qtforandroid --init-classes=
icon.filename = /home/gwhitlock/Desktop/workspace/VerseLens/assets/verselens_icon.png

[buildozer]
log_level = 2
warn_on_root = 1
bin_dir = /home/gwhitlock/Desktop/workspace/VerseLens

