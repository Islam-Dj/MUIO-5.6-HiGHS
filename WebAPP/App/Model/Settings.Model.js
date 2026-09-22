import { UNITS } from "../../Classes/Const.Class.js";

export class Model {
    constructor () {
        this.units = UNITS;
        this.lstgPageSize = localStorage.getItem("osy-pagesize");;
        this.lstgDecimalPoints =  localStorage.getItem("osy-decimalpoints");  
        this.lstgUnits = JSON.parse(localStorage.getItem("osy-units"));
    }
}