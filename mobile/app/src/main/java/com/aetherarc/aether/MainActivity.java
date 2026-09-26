package com.aetherarc.aether;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.net.Uri;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private WebView webView;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        webView = new WebView(this);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        webView.setWebViewClient(new WebViewClient());
        webView.addJavascriptInterface(new AetherBridge(), "AndroidAether");
        setContentView(webView);
        webView.loadUrl("file:///android_asset/index.html");
        handleIntent(getIntent());
    }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        handleIntent(i);
    }

    private void handleIntent(Intent i) {
        Uri u = i == null ? null : i.getData();
        if (u != null && "aether".equals(u.getScheme()) && "auth".equals(u.getHost())) {
            String t = u.getQueryParameter("access_token");
            if (t != null && !t.isEmpty()) webView.post(() -> webView.evaluateJavascript("window.__aetherOAuthToken(" + JSONObject.quote(t) + ")", null));
        }
    }

    private final class AetherBridge {
        @JavascriptInterface public String getBackendUrl() { return BuildConfig.AETHER_BACKEND_URL; }
        @JavascriptInterface public void openExternal(final String url) { try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) {} }

        @JavascriptInterface public void chat(final String id, final String authToken, final String body) {
            request("POST", id, BuildConfig.AETHER_BACKEND_URL + "/api/chat", authToken == null || authToken.isEmpty() ? "" : "Bearer " + authToken, body);
        }
        @JavascriptInterface public void postJson(final String id, final String url, final String auth, final String body) { request("POST", id, url, auth, body); }
        @JavascriptInterface public void getJson(final String id, final String url, final String auth) { request("GET", id, url, auth, null); }

        private void request(final String method, final String id, final String url, final String auth, final String body) {
            new Thread(() -> {
                boolean ok = false; int code = 0; String response; HttpURLConnection c = null;
                try {
                    c = (HttpURLConnection)new URL(url).openConnection();
                    c.setRequestMethod(method); c.setConnectTimeout(15000); c.setReadTimeout(90000); c.setDoInput(true);
                    c.setRequestProperty("Accept","application/json"); c.setRequestProperty("Cache-Control","no-cache");
                    if (auth != null && !auth.isEmpty()) c.setRequestProperty("Authorization",auth);
                    if ("POST".equals(method)) {
                        c.setDoOutput(true); c.setRequestProperty("Content-Type","application/json; charset=utf-8");
                        byte[] bytes=(body==null?"":body).getBytes(StandardCharsets.UTF_8); c.setFixedLengthStreamingMode(bytes.length);
                        try(OutputStream o=c.getOutputStream()){o.write(bytes);}
                    }
                    code=c.getResponseCode(); InputStream in=code>=200&&code<300?c.getInputStream():c.getErrorStream(); response=readAll(in); ok=code>=200&&code<300;
                } catch(Exception e) { response=e.getMessage()==null?e.getClass().getSimpleName():e.getMessage(); }
                finally { if(c!=null)c.disconnect(); }
                final String r=build(ok,code,response);
                webView.post(() -> webView.evaluateJavascript("window.__aetherNativeResponse("+JSONObject.quote(id)+","+JSONObject.quote(r)+")",null));
            }).start();
        }

        private String readAll(InputStream in) throws IOException {
            if(in==null)return ""; BufferedReader r=new BufferedReader(new InputStreamReader(in,StandardCharsets.UTF_8)); StringBuilder b=new StringBuilder(); String l;
            while((l=r.readLine())!=null)b.append(l); r.close(); return b.toString();
        }
        private String build(boolean ok,int code,String body) {
            try { JSONObject o=new JSONObject(); o.put("ok",ok); o.put("code",code); o.put("body",body==null?"":body); return o.toString(); }
            catch(Exception e) { return "{\"ok\":false,\"code\":500,\"body\":\"native bridge error\"}"; }
        }
    }

    @Override public void onBackPressed() { if(webView!=null&&webView.canGoBack())webView.goBack();else super.onBackPressed(); }
}