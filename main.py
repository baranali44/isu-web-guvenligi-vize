#!/usr/bin/env python3
import argparse
import sys
from src.log_hunter import MSFWebDetector

def main():
    parser = argparse.ArgumentParser(description="ISU Web Güvenliği - MSF Log Tespit Sistemi")
    parser.add_argument("-l", "--log", required=True, help="Analiz edilecek web sunucu log dosyası (örn: access.log)")
    args = parser.parse_args()

    detector = MSFWebDetector()
    try:
        with open(args.log, 'r', encoding='utf-8') as f:
            logs = f.readlines()
    except FileNotFoundError:
        print(f"[X] Hata: Log dosyası bulunamadı -> {args.log}")
        sys.exit(1)

    results = detector.analyze_access_log(logs)

    print("\n" + "="*60)
    print(" 🛡️  METASPLOIT WEB SALDIRI LOG ANALİZ RAPORU")
    print("="*60)
    
    if results:
        for alert in results:
            print(f"\033[91m[!] SALDIRI TESPİTİ (Satır {alert['line']}): {alert['attack']}\033[0m")
            print(f"    Log Verisi: {alert['payload'][:90]}...\n")
    else:
        print("\033[92m[+] Sunucu logları temiz. Bilinen Metasploit web imzası bulunamadı.\033[0m")

if __name__ == "__main__":
    main()
