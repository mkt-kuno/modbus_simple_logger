# Simple Logger App for Trio/Quartet/Yamanin
Python3.10 以上で動作可能なシンプルなModbusロガーです  
データ出力先は APPDATAの先にsqlite3だけという、こちらもシンプルな仕組みです。  

既存のPython環境を破壊しないためにも、AnacondaやMinicondaでPython環境を構築するか、  
PyenvやvenvなどのPythonで標準的な環境切り分け、  
もしくはEmbeddedPythonやPypyなど、ポータブル版のPythonでpipすることをお勧めします。  

動作にはCOMポートの書き換えのみPythonコードの変更が必要かと思っていますが、ほかにあればissueをあげてください。  

[Trio/Quartet](https://github.com/mkt-kuno/quartet)  
[Yamanin](https://github.com/mkt-kuno/yamanin)  
