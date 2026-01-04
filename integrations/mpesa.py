# pesaflow/integrations/mpesa.py

class MpesaSTKPush:
    """Dummy MPESA STK Push class for now"""
    
    def __init__(self, phone_number, amount, account_reference, transaction_desc):
        self.phone_number = phone_number
        self.amount = amount
        self.account_reference = account_reference
        self.transaction_desc = transaction_desc
    
    def initiate_stk_push(self):
        """Initiate STK push"""
        # This is a placeholder for actual MPESA integration
        print(f"STK Push initiated for {self.phone_number}")
        return {
            "status": "success",
            "message": "STK push initiated successfully",
            "phone_number": self.phone_number,
            "amount": self.amount
        }
    
    @staticmethod
    def callback_handler(data):
        """Handle MPESA callback"""
        return {"status": "success", "data": data}