from datetime import datetime
import resend

def emailHtml(code: str, title: str, message: str, expiry_minutes: int = 15) -> str:
    htmlcontent = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7f7f7; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 8px; padding: 30px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #333;">{title}</h2>
            <p style="font-size: 16px; color: #555;">{message}</p>
            <div style="margin: 20px 0;">
                <span style="font-size: 24px; font-weight: bold; color: #1a73e8; background-color: #e8f0fe; padding: 10px 20px; border-radius: 6px;">{code}</span>
            </div>
            <p style="font-size: 14px; color: #555;">This code will expire in {expiry_minutes} minutes. Requesting a new code will expire the previous one.</p>
            <p style="font-size: 14px; color: #888;">If you did not request this, you can ignore this email.</p>
            <p style="font-size: 14px; color: #888;">&copy; {datetime.now().year} "Kairo"</p>
        </div>
    </body>
    </html>
    """
    return htmlcontent

async def sendEmail(sender : str, reciever : str, subject : str, html : str):
    try:
        resend.Emails.send({
            "from": sender,
            "to": reciever,
            "subject": subject,
            "html": html
        })
        return {"success": True}
    except Exception as error:
        return {"success": False, "message": "Internal Server Error"}