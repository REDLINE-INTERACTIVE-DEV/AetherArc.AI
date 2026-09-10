# Aether Android client

This folder is a real Android Studio project for the Aether mobile client. It builds an APK that contains the Aether interface and connects to the existing FastAPI backend.

## Build an APK

1. Open the `mobile/` folder in Android Studio.
2. Let Gradle sync.
3. Build > Build APK(s), or run `gradle assembleDebug` from the `mobile/` folder.
4. The debug APK is created at `mobile/app/build/outputs/apk/debug/app-debug.apk`.

The project uses Android Gradle Plugin 8.6.1, Gradle 8.7, Java 17 and compile/target SDK 35.

## Connect the app

On first launch, enter the URL of the machine running Aether's FastAPI backend. Android Emulator can reach a host computer with `http://10.0.2.2:8000`. A physical phone on the same Wi-Fi should use the computer's LAN address, such as `http://192.168.1.10:8000`.

For public deployment, use HTTPS and keep all model/API secrets on the backend. Never put provider API keys in the APK.
