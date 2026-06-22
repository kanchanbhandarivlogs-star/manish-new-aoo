package com.collegeop.adsstudio;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Native Android back button must navigate the WebView history instead of
        // killing the activity. The Capacitor BridgeActivity already handles this
        // when web routes accept back navigation; we just enable that behaviour.
        bridge.getWebView().setOnKeyListener((v, keyCode, event) -> {
            if (keyCode == android.view.KeyEvent.KEYCODE_BACK
                    && event.getAction() == android.view.KeyEvent.ACTION_UP
                    && bridge.getWebView().canGoBack()) {
                bridge.getWebView().goBack();
                return true;
            }
            return false;
        });
    }
}
