import re

class MSFWebDetector:
    """Web sunucu loglarında (Apache/Nginx) Metasploit saldırı imzalarını arayan analiz motoru."""
    
    def __init__(self):
        # Metasploit'in popüler web exploitlerine ait HTTP İstek imzaları
        self.signatures = {
            "MSF_DIR_SCANNER": r"GET \/[a-zA-Z0-9_-]+\/ HTTP\/1\.1.*Nikto|Metasploit",
            "PHP_CGI_RCE": r"GET \/\?-\%64[\+\s]+allow_url_include\%3d1",
            "APACHE_STRUTS_EXPLOIT": r"Content-Type:\s*%{#context\[\'com\.opensymphony\.xwork2\.dispatcher\.HttpServletResponse\'\]",
            "WEB_SHELL_UPLOAD": r"POST \/.*\.php\?cmd=.* HTTP\/1\.1"
        }

    def analyze_access_log(self, log_lines):
        alerts = []
        for line_no, line in enumerate(log_lines, 1):
            for attack_name, pattern in self.signatures.items():
                if re.search(pattern, line, re.IGNORECASE):
                    alerts.append({
                        "line": line_no, 
                        "attack": attack_name, 
                        "payload": line.strip()
                    })
        return alerts
