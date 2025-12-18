#include <Arduino.h>
#include <WiFi.h>
#include <esp_wifi.h>

void setup() {
    Serial.begin(115200);
    delay(2000); // Wait for serial connection

    // Initialize WiFi in Station mode to get the correct MAC for ESP-NOW
    WiFi.mode(WIFI_STA);
    
    Serial.println("\n\n=================================================");
    Serial.println("ESP32 MAC Address Finder");
    Serial.println("=================================================");
    
    Serial.print("MAC Address: ");
    Serial.println(WiFi.macAddress());
    
    Serial.println("=================================================");
    Serial.println("Copy this MAC address for your configuration.");
    Serial.println("=================================================\n");
}

void loop() {
    // Print every 5 seconds just in case
    delay(5000);
    Serial.print("MAC Address: ");
    Serial.println(WiFi.macAddress());
}
