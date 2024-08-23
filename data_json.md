# About Data Json
## JSON root 構造
|/|Type|備考|
|----|----|----|
|env|dict|オプション,環境変数とかバージョンとか|
|key|dict|必須|
|data|list|必須、中身は次セクションにあるdict|
|label|dict|オプション,ラベル情報,{key}の分はなくてもいい|
|unit|dict|オプション,単位情報,{key}の分はなくてもいい|

## JSON root["data"] 構造
|/data/|Type|備考|
|----|----|----|
|index|int|必須<br>-1:リアルタイム情報<br>0以上:DBデータ等、取得済みデータ列への参照インデックス|
|time|int(推奨)/<br>float/string| {%Y-%m-%d %H:%M:%S.%f} を推奨、次点エポック秒/ミリ秒|
|{key}|int/float/<br>string(非推奨)|必須、その他データ<br>{key}に対応するデータは必須|

## データソース
Websocket(リアルタイム表示用)  
HTTP-GET (計測中データ用)