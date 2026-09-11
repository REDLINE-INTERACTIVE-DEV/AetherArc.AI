package com.aetherarc.aether;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        webView.setWebViewClient(new WebViewClient());
        webView.addJavascriptInterface(new AetherBridge(), "AndroidAether");
        setContentView(webView);
        webView.loadUrl("file:///android_asset/index.html");
    }

    private final class AetherBridge {
        @JavascriptInterface
        public void chat(final String requestId, final String token, final String body) {
            new Thread(() -> {
                String response;
                boolean ok = false;
                int code = 0;
                try {
                    URL url = new URL("https://router.huggingface.co/v1/chat/completions");
                    HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setConnectTimeout(20000);
                    conn.setReadTimeout(90000);
                    conn.setDoOutput(true);
                    conn.setRequestProperty("Content-Type", "application/json");
                    conn.setRequestProperty("Authorization", "Bearer " + token);
                    byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
                    conn.setFixedLengthStreamingMode(bytes.length);
                    try (OutputStream out = conn.getOutputStream()) {
                        out.write(bytes);
                    }
                    code = conn.getResponseCode();
                    InputStream stream = code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream();
                    response = readAll(stream);
                    ok = code >= 200 && code < 300;
                    conn.disconnect();
                } catch (Exception e) {
                    response = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                }
                final String result = buildResult(ok, code, response);
                webView.post(() -> webView.evaluateJavascript(
                        "window.__aetherNativeResponse(" + JSONObject.quote(requestId) + "," + JSONObject.quote(result) + ")",
                        null));
            }).start();
        }
    }

    private String readAll(InputStream stream) throws Exception {
        if (stream == null) return "";
        StringBuilder out = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) out.append(line);
        }
        return out.toString();
    }

    private String buildResult(boolean ok, int code, String body) {
        try {
            JSONObject result = new JSONObject();
            result.put("ok", ok);
            result.put("code", code);
            result.put("body", body == null ? "" : body);
            return result.toString();
        } catch (Exception e) {
            return "{\"ok\":false,\"code\":500,\"body\":\"native bridge error\"}";
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}
