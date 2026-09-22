import { Message } from "../../Classes/Message.Class.js";
import { Base } from "../../Classes/Base.Class.js";
import { Html } from "../../Classes/Html.Class.js";
import { Osemosys } from "../../Classes/Osemosys.Class.js";
import { Model } from "../Model/DataFile.Model.js";
import { MessageSelect } from "./MessageSelect.js";
import { DefaultObj } from "../../Classes/DefaultObj.Class.js";
import { Sidebar } from "./Sidebar.js";

export default class DataFile {
    static onLoad() {
        Message.loaderStart('Loading data...');
        Base.getSession()
            .then(response => {
                let casename = response.session;
                const promise = [];
                promise.push(casename);
                let genData = Osemosys.getData(casename, 'genData.json');
                promise.push(genData);
                const resData = Osemosys.getResultData(casename, 'resData.json');
                promise.push(resData);
                const modelFile = Osemosys.readModelFile();
                promise.push(modelFile);
                return Promise.all(promise);
            })
            .then(data => {
                let [casename, genData, resData, modelFile] = data;
                let model = new Model(casename, genData, resData, modelFile, "DataFile");
                if (casename) {
                    this.initPage(model);
                } else {
                    Message.loaderEnd();
                    MessageSelect.init(DataFile.refreshPage.bind(DataFile));
                }
            })
            .catch(error => {
                Message.loaderEnd();
                Message.danger(error);
            });
    }

    static initPage(model) {
        Message.clearMessages();
        //console.log('model ', model)
        //Navbar.initPage(model.casename, model.pageId);
        Html.title(model.casename, model.title, "");
        Html.renderCases(model.cases);
        Html.renderModelFile(model.modelFile);
        //potrebno je napraviti render svih scenarija (mozda je dodan novi scenario u medjuvremenu), on mora biti dodan u listu scenarija po case run samo sto nece biti aktivan
        // Html.renderScOrder(model.scBycs[model.cs]);
        //console.log('model.scenarios ',model.scenarios)
        Html.renderScOrder(model.scenarios);
        if (model.casename == null) {
            Message.info("Please select model or create new Model!");
        }
        if (model.scenariosCount > 1) {
            $('#scCommand').show();
        }
        //loadScript("References/smartadmin/js/plugin/jquery-nestable/jquery.nestable.min.js", Nestable.init.bind(null));
        pageSetUp();
        this.initEvents(model);
    }

    static refreshPage(casename) {
        Message.loaderStart('Loading data...');
        Base.setSession(casename)
            .then(response => {
                Message.clearMessages();
                const promise = [];
                promise.push(casename);
                let genData = Osemosys.getData(casename, 'genData.json');
                promise.push(genData);
                const resData = Osemosys.getResultData(casename, 'resData.json');
                promise.push(resData);
                const modelFile = Osemosys.readModelFile();
                promise.push(modelFile);
                return Promise.all(promise);
            })
            .then(data => {
                let [casename, genData, resData, modelFile] = data;
                let model = new Model(casename, genData, resData, modelFile, "DataFile");
                $(".DataFile").hide();
                $("#osy-DataFile").empty();
                $("#osy-runOutput").empty();
                $("#osy-lpOutput").empty();
                // $("#osy-downloadDataFile").hide();
                // $("#osy-downloadResultsFile").hide();
                $("#osy-solver").hide();
                $("#osy-run").hide(); $("#osy-solverSelect").hide(); window.syncHighsOptionsButton && window.syncHighsOptionsButton();
                $(".runOutput").hide();
                $(".lpOutput").hide(); $(".highsOutput").hide();
                $(".Results").hide();
                DataFile.initPage(model);
                DataFile.initEvents(model);
            })
            .catch(error => {
                Message.loaderEnd();
                Message.bigBoxInfo(error);
            })
    }

    static initEvents(model) {
        $("#casePicker").off('click');
        $("#casePicker").on('click', '.selectCS', function (e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            var casename = $(this).attr('data-ps');
            Html.updateCasePicker(casename);
            DataFile.refreshPage(casename);
            Message.smallBoxInfo("Case selection", casename + " is selected!", 3000);
        });

        $("#osy-logFile").off('click');
        $("#osy-logFile").on('click', function (event) {
            Message.loaderStart('Generating log file!')
            Osemosys.readLogFile()
            .then(response => {
                Message.loaderEnd();
                console.log('resposne ', response)
                $("#osy-logFiletxt").html('<pre class="log-output">'+response+'</pre>');
                $("#osy-LogFileModal").modal("show");
                //$("#osy-logFiletxt").html('<pre class="log-output">'+response+'</pre>');
                // if (response.status_code == "success") {
                //     //$("#osy-LogFileModal").toggle();
                // }
            })
            .catch(error => {
                Message.loaderEnd();
                Message.bigBoxDanger('Error message', error, null);
            })
        });

        $("#osy-btnScOrder").off('click');
        $("#osy-btnScOrder").on('click', function (event) {
            // console.log('model, ', model)
            // console.log('model.scenarios ',model.scenarios);
            // console.log('model.scBycs[model.cs] ',model.scBycs)
            if(model.cs in  model.scBycs){
                Html.renderScOrder( model.scBycs[model.cs]);
            }else{
                Html.renderScOrder(model.scenarios);
            }

            //nove scenarije dodjeamo sad u modelu ovaj dio je nepotreban
            // if(model.cs in  model.scBycs){
            //     //pored originalnih scenarija u caserunu, potrebno dodati eventualno nove
            //     //scenarije koji su dodani poslije uspjesnog RUN-a, kao neaktivne
            //     let sccsMap = {};
            //     $.each(model.scBycs[model.cs], function (id, scObj) {
            //         sccsMap[scObj.ScenarioId] = scObj;
            //     });
            //     //create shallow copy of array
            //     let scArray = model.scBycs[model.cs].slice()
            //     $.each(model.scenarios, function (key, obj) {
            //         if(obj.ScenarioId in sccsMap === false){
            //             console.log('obj.Scenario ', obj.Scenario)
            //             let sc = JSON.parse(JSON.stringify(obj));
            //             sc.Active = false;
            //             console.log('sc ', sc)
            //             scArray.push(sc);
            //         }
            //     });
            //     Html.renderScOrder(scArray);
            // }else{
            //     Html.renderScOrder(model.scenarios);
            // }

        });

        function setAllCheckboxes(state) {
            // Targetiramo checkboxove SAMO u #osy-scOrder (SC_0 ostaje netaknut jer je disabled i u #osy-sc0)
            $('#osy-scOrder input[type="checkbox"]:not(:disabled)')
                .prop('checked', state)
                .trigger('change'); // ako imaÅ¡ logiku na change eventu
        }

        $("#toggle-all").off('click');
        $('#toggle-all').on('click', function (e) {
            
            e.preventDefault();
            e.stopPropagation();

            const $btn = $(this);
            // Skup svih "normalnih" checkboxova (osim disabled i osim SC_0)
            const $boxes = $('#osy-scOrder input[type="checkbox"]:not(:disabled)');
            // Provjera: ima li ijedan neÄekiran?
            const anyUnchecked = $boxes.is(':not(:checked)');

            // Ako ima neÄekiranih â†’ Äekiraj sve, inaÄe â†’ poniÅ¡ti sve
            setAllCheckboxes(anyUnchecked);

            // AÅ¾uriraj label dugmeta da bude intuitivna
            //$btn.text(anyUnchecked ? 'Uncheck all' : 'Check all');
            const $icon = $btn.find('i.fa');
            if (anyUnchecked) {
                // Sada su SVI Äekirani -> prikaÅ¾i "poniÅ¡ti" ikonu
                $icon.removeClass('fa-square-o').addClass('fa-check-square-o');
                $btn.find('span').text('Uncheck all'); // ili ukloni ovu liniju ako Å¾eliÅ¡ samo ikonu
            } else {
                // Sada su SVI odÄekirani -> prikaÅ¾i "odaberi" ikonu
                $icon.removeClass('fa-check-square-o').addClass('fa-square-o');
                $btn.find('span').text('Check all'); // ili ukloni ovu liniju ako Å¾eliÅ¡ samo ikonu
            }

        });


        $("#btnSaveOrder").off('click');
        $("#btnSaveOrder").on('click', function (event) {
            Message.clearMessages();
            Message.bigBoxWarning('Scenario Order Updated', 'You have updated the order of scenarios. To apply your changes, please click Update Case.', 4000);
            $('#osy-order').modal('toggle');

            //nema potrebe da spasavmo scenario order jer se on ada nalazi u resData
            // let order = $("#osy-scOrder").jqxSortable("toArray")
            // var scAcitive = new Array();
            // $.each($('input[type="checkbox"]:checked'), function (key, value) {
            //     scAcitive.push($(value).attr("id"));
            // });
            // let scOrder = DefaultObj.defaultScenario(true);

            // $.each(order, function (id, sc) {
            //     let tmp = {};
            //     if (scAcitive.includes(sc)) {
            //         tmp['ScenarioId'] = sc;
            //         tmp['Scenario'] = model.scMap[sc]['Scenario'];
            //         tmp['Desc'] = model.scMap[sc]['Desc'];
            //         tmp['Active'] = true
            //     } else {
            //         tmp['ScenarioId'] = sc;
            //         tmp['Scenario'] = model.scMap[sc]['Scenario'];
            //         tmp['Desc'] = model.scMap[sc]['Desc'];
            //         tmp['Active'] = false;
            //     }
            //     scOrder.push(tmp);
            // });

            // Osemosys.saveScOrder(scOrder, model.casename)
            // .then(response => {
            //     if (response.status_code == "success") {
            //         $('#osy-order').modal('toggle');
            //         model.scenarios = scOrder;
            //         Message.clearMessages();
            //         Message.bigBoxSuccess('Sceanario order', response.message, 3000);
            //         //sync S3
            //         if (Base.AWS_SYNC == 1) {
            //             Base.updateSync(model.casename, "genData.json");
            //         }
            //     }
            // })
            // .catch(error => {
            //     Message.bigBoxDanger('Error message', error, null);
            // })
        });

        $("#osy-caseRun").jqxValidator({
            hintType: 'label',
            animationDuration: 500,
            rules: [
                { input: '#osy-casename', message: "Case name is required field!", action: 'keyup', rule: 'required' },
                {
                    input: '#osy-casename', message: "Entered case name is not allowed!", action: 'keyup', rule: function (input, commit) {
                        var casename = $("#osy-casename").val();
                        var result = (/^[a-zA-Z0-9-_ ]*$/.test(casename));
                        return result;
                    }
                }
            ]
        });

        let update = false;
        $("#osy-createCaseRun").off('click');
        $("#osy-createCaseRun").on('click', function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();
            $("#osy-caseRun").jqxValidator('validate')
        });

        $("#osy-updateCaseRun").off('click');
        $("#osy-updateCaseRun").on('click', function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();
            update = true;
            $("#osy-caseRun").jqxValidator('validate')
        });

        $("#osy-newCaseRun").off('click');
        $("#osy-newCaseRun").on('click', function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();
            update = false;
            Html.title(model.casename, model.title, "");
            Html.renderScOrder(model.scenarios);
            model.cs = '';
            Message.clearMessages();
            $("#osy-casename").val(null);
            $("#osy-desc").val(null);
            $('#tabs a[href="#tabCases"]').tab('show');
            $("#osy-createCaseRun").show();
            $("#osy-updateCaseRun").hide();
            $("#osy-newCaseRun").hide();

            $("#osy-runCaseDiv").hide();
            $("#osy-generateDataFile").hide();
            $("#osy-solver").hide();
            $("#osy-run").hide(); $("#osy-solverSelect").hide(); window.syncHighsOptionsButton && window.syncHighsOptionsButton();

            $(".runOutput").hide();
            $(".lpOutput").hide(); $(".highsOutput").hide();
            $(".DataFile").hide();
            $(".Results").hide();

            $(".batchOutput").hide();
            $("#osy-batchRun").hide();
            $('.checkbox').prop('checked', false);
        });

        $("#osy-caseRun").off('validationSuccess');
        $("#osy-caseRun").on('validationSuccess', function (event) {
            event.preventDefault();
            event.stopImmediatePropagation();
            Pace.restart();

            var caserunname = $("#osy-casename").val();
            let oldcaserunname = model.cs;
            var desc = $("#osy-desc").val();

            let order = $("#osy-scOrder").jqxSortable("toArray")
            var scAcitive = new Array();

            $.each($('input[type="checkbox"]:checked'), function (key, value) {
                scAcitive.push($(value).attr("id"));
            });

            let scOrder = DefaultObj.defaultScenario(true);
            $.each(order, function (id, sc) {
                let tmp = {};
                if (scAcitive.includes(sc)) {
                    tmp['ScenarioId'] = sc;
                    tmp['Scenario'] = model.scMap[sc]['Scenario'];
                    tmp['Desc'] = model.scMap[sc]['Desc'];
                    tmp['Active'] = true
                } else {
                    tmp['ScenarioId'] = sc;
                    tmp['Scenario'] = model.scMap[sc]['Scenario'];
                    tmp['Desc'] = model.scMap[sc]['Desc'];
                    tmp['Active'] = false;
                }
                scOrder.push(tmp);
            });

            let caseId = DefaultObj.getId('CS');

            let caseData = {
                "Case": caserunname,
                "CaseId": caseId,
                "Desc": desc,
                "Runtime": Date().toLocaleString('en-US', { hour12: false, hour: "numeric", minute: "numeric" }),
                "Scenarios": scOrder
            }

            if (update) {
                Osemosys.updateCaseRun(model.casename, caserunname, oldcaserunname, caseData)
                .then(response => {
                    Message.clearMessages();
                    if (response.status_code == 'success') {
                        model.cs = caserunname;
                        $.each(model.cases, function (id, cs) {
                            if (cs.Case == oldcaserunname) {
                                model.cases[id] = caseData;
                            }
                        });
                        model.scBycs[model.cs] = scOrder;
                        Html.title(model.casename, model.title, caserunname);
                        Html.renderCases(model.cases);
                        $('#tabs a[href="#tabCases"]').tab('show');
                        $("#osy-runCaseDiv").show();
                        $("#osy-caseRunName").text(caserunname);
                        $('#osy-generateDataFile').show();
                        $("#osy-newCaseRun").show();
                        $(".DataFile").hide();
                        $(".runOutput").hide();
                        $(".lpOutput").hide(); $(".highsOutput").hide();
                        $(".Results").hide();
                        $(".batchOutput").hide();
                        $("#osy-batchRun").hide();
                        $('.checkbox').prop('checked', false);
                        Message.smallBoxInfo('Generate message', response.message, 3000);
                    }
                    if (response.status_code == 'exist') {
                        Message.smallBoxWarning('Generate message', response.message, 3000);
                    }
                })
                .catch(error => {
                    Message.bigBoxDanger('Error message', error, null);
                })
            } else {
                Osemosys.createCaseRun(model.casename, caserunname, caseData)
                .then(response => {
                    Message.clearMessages();
                    if (response.status_code == 'success') {
                        $("#osy-runCaseDiv").show();
                        $("#osy-caseRunName").text(caserunname);
                        $('#osy-generateDataFile').show();
                        model.cs = caserunname;
                        model.cases.push(caseData);
                        model.scBycs[model.cs] = scOrder;
                        $("#osy-createCaseRun").hide();
                        $("#osy-updateCaseRun").show();
                        $("#osy-newCaseRun").show();

                        $(".batchOutput").hide();
                        $("#osy-batchRun").hide();
                        $('.checkbox').prop('checked', false);
                        Html.renderCases(model.cases);
                        Html.title(model.casename, model.title, caserunname);
                        Message.smallBoxInfo('Generate message', response.message, 3000);
                    }
                    if (response.status_code == 'exist') {
                        Message.smallBoxWarning('Generate message', response.message, 3000);
                    }
                })
                .catch(error => {
                    Message.bigBoxDanger('Error message', error, null);
                })
            }

        });

        $("#osy-generateDataFile").off('click');
        $("#osy-generateDataFile").on('click', function (event) {
            Pace.restart();
            Message.loaderStart('Generating data file!')
            Osemosys.generateDataFile(model.casename, model.cs)
            .then(response => {
                if (response.status_code == "success") {
                    const promise = [];
                    let DataFile = Osemosys.readDataFile(model.casename, model.cs);
                    promise.push(DataFile);
                    promise.push(response.message);
                    return Promise.all(promise);
                }
            })
            .then(response => {
                let [DataFile, message] = response;
                $(".DataFile").show();
                $("#osy-runOutput").empty();
                $("#osy-lpOutput").empty();
                $(".runOutput").hide();
                $(".lpOutput").hide(); $(".highsOutput").hide();
                $(".Results").hide();
                $(".batchOutput").hide();
                Html.renderDataFile(DataFile, model)
                ///////////////////////////////////////////////////////////////////
                //$("#osy-downloadDataFile").show();
                //ne moramo updateovati S3 sa data file
                // if (Base.AWS_SYNC == 1){
                //     Base.updateSync(model.casename, "data.txt");
                // }
                if (Base.HEROKU == 0) {
                    $("#osy-run").show(); $("#osy-solverSelect").show(); window.syncHighsOptionsButton && window.syncHighsOptionsButton();
                    //$("#osy-solver").show();
                }
                //Message.clearMessages();
                //Message.bigBoxSuccess('Generate message', message, 3000);
                Message.loaderEnd();
                Message.smallBoxInfo('Generate message', message, 3000);
            })
            .catch(error => {
                Message.loaderEnd();
                Message.bigBoxDanger('Error message', error, null);
            })
        });

        $("#osy-run").off('click');
        $("#osy-run").on('click', function (event) {
            Pace.restart();
            Message.loaderStart('Optimization in process!')

            
            // const logBox = document.getElementById("logBox");
            // const eventSource = new EventSource("http://127.0.0.1:5002/stream_logs");

            // eventSource.onmessage = function (e) {
            //     console.log('e.data ', e.data)
            //     logBox.innerHTML += e.data + "<br>";
            //     logBox.scrollTop = logBox.scrollHeight;   // auto-scroll
            // };





            //////////////////////////////////////////////////////////////////////////////////////

            //solver chosen in the toolbar dropdown (cbc | glpk | highs | highs-mosox); CBC stays the default
            let solver = $('#osy-solverSelect').val() || 'cbc';
            //settings from the HiGHS panel; null for CBC and GLPK, which ignore them
            let highsOptions = (typeof window.readHighsOptions === 'function' && solver.indexOf('highs') === 0)
                ? window.readHighsOptions() : null;
            //the loading circle becomes the progress display: it names the stage,
            //counts its seconds, and shows how far the run has got
            startRunProgress(model.casename, model.cs);
            Osemosys.run(model.casename, solver, model.cs, highsOptions)
            .then(response => {
                stopRunProgress(model.casename, model.cs);
                Message.clearMessages();
                //console.log('response ',response)
                if (response.status_code == "success") {
                    Message.loaderEnd();
                    $(".runOutput").show();
                    $(".lpOutput").show();
                    $(".Results").show();
                    $(".batchOutput").hide();
                    $("#osy-batchOutput").empty();
                    $("#osy-runOutput").empty();
                    $("#osy-runOutput").html('<pre class="log-output">' + response.cbc_message, response.cbc_stdmsg+ '</pre>');
                    $("#osy-lpOutput").empty();
                    $("#osy-lpOutput").html('<pre class="log-output">' + response.glpk_message, response.glpk_stdmsg+ '</pre>');
                    $("#osy-highsOutput").empty();
                    if (response.highs_message) {
                        $(".highsOutput").show();
                        $("#osy-highsOutput").html('<pre class="log-output">' + response.highs_message + '</pre>');
                    } else {
                        $(".highsOutput").hide();
                    }
                    Base.getResultCSV(model.casename, model.cs)
                        .then(csvs => {
                            Html.renderCSV(csvs, model.cs)
                        });
                    Sidebar.Reload(model.casename);
                    Message.clearMessages();
                    Message.successOsy( response.timer);
                    Message.bigBoxSuccess('Run message', response.timer, 3000);
                }
                if (response.status_code == "warning") {
                    Message.loaderEnd();
                    $(".runOutput").show();
                    $(".lpOutput").show();
                    $(".Results").show();
                    $(".batchOutput").hide();
                    $("#osy-batchOutput").empty();
                    $("#osy-runOutput").empty();
                    $("#osy-runOutput").html('<pre class="log-output">' + response.cbc_message, response.cbc_stdmsg+ '</pre>');
                    $("#osy-lpOutput").empty();
                    $("#osy-lpOutput").html('<pre class="log-output">' + response.glpk_message, response.glpk_stdmsg+ '</pre>');
                    $("#osy-highsOutput").empty();
                    if (response.highs_message) {
                        $(".highsOutput").show();
                        $("#osy-highsOutput").html('<pre class="log-output">' + response.highs_message + '</pre>');
                    } else {
                        $(".highsOutput").hide();
                    }
                    Base.getResultCSV(model.casename, model.cs)
                        .then(csvs => {
                            Html.renderCSV(csvs, model.cs)
                        });
                    Sidebar.Reload(model.casename);
                    Message.clearMessages();
                    Message.warningOsy( response.timer );
                }
                if (response.status_code == "error") {
                    Message.loaderEnd();
                    $(".runOutput").show();
                    $(".lpOutput").show();
                    $(".Results").show();
                    $(".batchOutput").hide();
                    $("#osy-batchOutput").empty();
                    $("#osy-runOutput").empty();
                    $("#osy-runOutput").html('<pre class="log-output">' + response.cbc_message, response.cbc_stdmsg+ '</pre>');
                    $("#osy-lpOutput").empty();
                    $("#osy-lpOutput").html('<pre class="log-output">' + response.glpk_message, response.glpk_stdmsg+ '</pre>');
                    $("#osy-highsOutput").empty();
                    if (response.highs_message) {
                        $(".highsOutput").show();
                        $("#osy-highsOutput").html('<pre class="log-output">' + response.highs_message + '</pre>');
                    } else {
                        $(".highsOutput").hide();
                    }
                    Message.clearMessages();
                    // let errormsg = '';
                    // if (response.glpk_message != "" || response.glpk_stdmsg != "") {
                    //     errormsg += 'Error occured during creation of LP file, GLPK run! See LP file (GLPK) log for more details. '
                    // }
                    // if (response.cbc_message != "" || response.cbc_stdmsg != "") {
                    //     errormsg += 'Error occured during optimization process, CBC run! See CBC solver log for more details.'
                    // }

                    // Message.dangerOsy(errormsg);
                    Message.dangerOsy( response.timer );
                }
            })
            .catch(error => {
                console.log('error ',error)
                Message.loaderEnd();
                Message.bigBoxDanger('Error message', error, null);
            })
        });

        //$("#osy-Cases").off('click');
        $("#osy-Cases").on('click', '.selectCS', function (e) {
            //$(document).delegate(".selectCS","click",function(e){
            e.preventDefault();
            e.stopImmediatePropagation();
            Html.renderScOrder( model.scBycs[model.cs]);
            Message.clearMessages();
            console.log('select, ', model)
            var caserunanme = $(this).attr('data-ps');
            model.cs = caserunanme;
            Html.renderScOrder( model.scBycs[model.cs]);

            Html.resData(model);
            Html.title(model.casename, model.title, caserunanme);

            $("#osy-createCaseRun").hide();
            $("#osy-updateCaseRun").show();
            $("#osy-newCaseRun").show();

            $("#osy-generateDataFile").hide();
            $("#osy-solver").hide();
            $("#osy-run").hide(); $("#osy-solverSelect").hide(); window.syncHighsOptionsButton && window.syncHighsOptionsButton();
            $("#osy-runCaseDiv").hide();

            $(".runOutput").hide();
            $(".lpOutput").hide(); $(".highsOutput").hide();
            $(".batchOutput").hide();
            $("#osy-batchRun").hide();
            $('.checkbox').prop('checked', false);

            Osemosys.readDataFile(model.casename, model.cs)
            .then(response => {
                let DataFile = response;
                const promise = [];
                promise.push(DataFile);
                let ResultCSV = Base.getResultCSV(model.casename, model.cs)
                promise.push(ResultCSV);
                return Promise.all(promise);
            })
            .then(data => {
                let [DataFile, ResultCSV] = data;
                console.log('data ', data)
                if (ResultCSV.length != 0) {
                    $(".Results").show();
                    Html.renderCSV(ResultCSV, model.cs)
                }
                if (DataFile) {
                    $(".DataFile").show();
                    $("#osy-runCaseDiv").show();
                    $("#osy-caseRunName").text(model.cs);
                    $("#osy-generateDataFile").show();

                    Html.renderDataFile(DataFile, model);
                }
                else if(!DataFile && ResultCSV.length == 0){
                    $(".DataFile").hide();
                    $(".Results").hide();
                    //$("#osy-generateDataFile").hide();

                    $("#osy-runCaseDiv").show();
                    $("#osy-caseRunName").text(model.cs);
                    $("#osy-generateDataFile").show();
                    Message.smallBoxWarning("Run case message", "Please generate data file!", 3000);
                }
            })
            .catch(error => {
                Message.danger(error);
            });
            Message.smallBoxInfo("Case selection", caserunanme + " is selected!", 3000);
        });


        //$("#osy-Cases").off('click');
        $("#osy-Cases").on('click', '.validateInputs', function (e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            Message.clearMessages();
            var caserunanme = $(this).attr('data-ps');
            //console.log('caserunanme ', caserunanme)
            Osemosys.validateInputs(model.casename, caserunanme)
            .then(response => {
                //console.log('response ', response)
                if (response.status_code == "success") {
                    $('#osy-validation').modal('toggle');
                    $("#valCasrunname").text(caserunanme)
                    $("#valOutput").html('<pre class="log-output">' + response.msg+ '</pre>')
                }
                if (response.status_code == "warning") {
                    $('#osy-validation').modal('toggle');
                    $("#valOutput").html('<pre class="log-output">' + response.msg+ '</pre>');
                }
                if (response.status_code == "error") {
                    //Message.warningOsy(response.msg);
                    Message.smallBoxWarning('Data file warning', response.msg, 8000)
                }
            })
            .catch(error => {
                Message.danger(error);
            });
        });

        //$(document).delegate(".deleteCase", "click", function (e) {
        // $(".deleteCase").off('click');
        // $(".deleteCase").on('click', function (e) {
        //$("#osy-Cases").off('click');
        $("#osy-Cases").on('click', '.deleteCase', function (e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            var caserunname = $(this).attr('data-ps');
            $.SmartMessageBox({
                title: "Confirmation Box!",
                content: "You are about to delete <b class='danger'>" + caserunname + "</b> case run! Are you sure?",
                buttons: '[No][Yes]'
            }, function (ButtonPressed) {
                if (ButtonPressed === "Yes") {
                    Message.loaderStart('Deleteing case data...');
                    Base.deleteCaseRun(model.casename, caserunname, false)
                        .then(response => {
                            Message.clearMessages();
                            Message.loaderEnd();
                            if (response.status_code == "success") {
                                Message.bigBoxSuccess('Delete message', response.message, 3000);
                                //REFRESH
                                Html.removeCase(caserunname);
                                //remove case from model
                                model.cases = model.cases.filter(function(el) { return el.Case != caserunname; });
                                delete model.scBycs[caserunname];

                                //relod sidebar
                                Sidebar.Reload(model.casename);

                                if (model.cs == caserunname || model.cs == ''){
                                    Html.title(model.casename, model.title, '');
                                    model.cs = null;
                                    $("#osy-casename").val(null);
                                    $("#osy-desc").val(null);
                                    $("#osy-createCaseRun").show();
                                    $("#osy-updateCaseRun").hide();
                                    $("#osy-newCaseRun").hide();

                                    $("#osy-generateDataFile").hide();
                                    $("#osy-runCaseDiv").hide();
                                    $("#osy-solver").hide();
                                    $("#osy-run").hide(); $("#osy-solverSelect").hide(); window.syncHighsOptionsButton && window.syncHighsOptionsButton();

                                    $(".runOutput").hide();
                                    $(".lpOutput").hide(); $(".highsOutput").hide();
                                    $(".DataFile").hide();
                                    $(".Results").hide();

                                    $(".batchOutput").hide();
                                    $("#osy-batchRun").hide();
                                    $('.checkbox').prop('checked', false);
                                }
                                //remove case from view json files
                                //sync with s3
                                if (Base.AWS_SYNC == 1) {
                                    SyncS3.deleteSync(caserunname);
                                }
                            }
                            // if(response.status_code=="success_session"){
                            //     Message.bigBoxSuccess('Delete message', response.message, 3000);
                            //     Message.info( "Please select existing or create new case to proceed!");
                            //     if (model.casename = casename){
                            //         // Sidebar.Load(null, null);
                            //         Sidebar.Reload(null);
                            //         //Routes.removeRoutes(model.PARAMETERS);
                            //     }
                            //     //REFRESH
                            //     Html.removeCase(casename);
                            //     if (Base.AWS_SYNC == 1){
                            //         Base.deleteSync(casename);
                            //     }
                            // }
                            if (response.status_code == "info") {
                                Message.info(response.message);
                            }
                            if (response.status_code == "warning") {
                                Message.warning(response.message);
                            }

                        })
                        .catch(error => {
                            console.log(error)
                            Message.danger(error);
                        });
                }
                if (ButtonPressed === "No") {
                    Message.bigBoxInfo("Confirmation message", "You pressed No...", 3000)
                }
            });
            //e.preventDefault();
            e.stopImmediatePropagation();
        });

        $("#osy-Cases").on('click', '.deleteCaseResults', function (e) {
            e.preventDefault();
            e.stopImmediatePropagation();
            var caserunname = $(this).attr('data-ps');
            $.SmartMessageBox({
                title: "Confirmation Box!",
                content: "You are about to delete <b class='danger'>" + caserunname + "</b> case run results! Are you sure?",
                buttons: '[No][Yes]'
            }, function (ButtonPressed) {
                if (ButtonPressed === "Yes") {
                    Message.loaderStart('Deleteing case results...');
                    Base.deleteCaseRun(model.casename, caserunname, true)
                        .then(response => {
                            Message.clearMessages();
                            Message.loaderEnd();
                            if (response.status_code == "success") {
                                Message.bigBoxSuccess('Delete message', response.message, 3000);
                                //REFRESH
                                //Html.removeCase(caserunname);
                                //remove case from model
                                //model.cases = model.cases.filter(function(el) { return el.Case != caserunname; });
                                //delete model.scBycs[caserunname];

                                //relod sidebar
                                Sidebar.Reload(model.casename);

                                if (model.cs == caserunname || model.cs == ''){
                                    Html.title(model.casename, model.title, '');
                                    model.cs = null;
                                    // $("#osy-casename").val(null);
                                    // $("#osy-desc").val(null);
                                    // $("#osy-createCaseRun").show();
                                    // $("#osy-updateCaseRun").hide();
                                    // $("#osy-newCaseRun").hide();

                                    // $("#osy-generateDataFile").hide();
                                    // $("#osy-runCaseDiv").hide();
                                    // $("#osy-solver").hide();
                                    // $("#osy-run").hide(); $("#osy-solverSelect").hide(); window.syncHighsOptionsButton && window.syncHighsOptionsButton();

                                    $(".runOutput").hide();
                                    $(".lpOutput").hide(); $(".highsOutput").hide();
                                    $(".DataFile").hide();
                                    $(".Results").hide();

                                    $(".batchOutput").hide();
                                    $("#osy-batchRun").hide();
                                    $("#osy-runCaseDiv").hide();
                                    $('.checkbox').prop('checked', false);
                                }
                                //remove case from view json files
                                //sync with s3
                                if (Base.AWS_SYNC == 1) {
                                    SyncS3.deleteSync(caserunname);
                                }
                            }

                            if (response.status_code == "info") {
                                Message.info(response.message);
                            }
                            if (response.status_code == "warning") {
                                Message.warning(response.message);
                            }

                        })
                        .catch(error => {
                            console.log(error)
                            Message.danger(error);
                        });
                }
                if (ButtonPressed === "No") {
                    Message.bigBoxInfo("Confirmation message", "You pressed No...", 3000)
                }
            });
            //e.preventDefault();
            e.stopImmediatePropagation();
        });

        //$(".Cases").off('click');
        $('#osy-Cases').on('click', '.checkbox', function(e){
            // var val = $(this).val();
            // $('input[value!='+val+'].checkboxgroup').attr('checked',false);
            let batchRunCases = [];
            $("input:checkbox[name=type]:checked").each(function(){
                batchRunCases.push($(this).val());
            });
            //console.log('batchRunCases ', batchRunCases)
            if(batchRunCases.length>1){
                //$("#osy-runCaseDiv").show();
                //$("#osy-caseRunName").text("BATCH RUN");
                $('#osy-batchRun').show();
            }
            else{
                //$("#osy-runCaseDiv").hide();
                $('#osy-batchRun').hide();
            }
          });

        $("#osy-batchRun").off('click');
        $("#osy-batchRun").on('click', function (event) {
            //console.log('BATCH RUN')
            Pace.restart();
            Message.loaderStart('BATCH RUN! Plese wait...');

            let batchRunCases = [];
            $("input:checkbox[name=type]:checked").each(function(){
                batchRunCases.push($(this).val());
            });

            Osemosys.batchRun(model.casename, batchRunCases)
            //Osemosys.generateDataFile(model.casename, batchRunCases[0])
            .then(response => {
                Message.loaderEnd();
                //Message.smallBoxInfo('Generate message', response.message, 3000);
                // console.log('response ', response.log);
                // Message.bigBoxDefault("BATCH RUN!", response.log)
                $(".runOutput").hide();
                $(".lpOutput").hide(); $(".highsOutput").hide();
                $(".Results").hide();
                $("#osy-runOutput").empty();
                $("#osy-lpOutput").empty();

                Sidebar.Reload(model.casename);
                Message.clearMessages();

                if(response.status == 'Success'){
                    Message.successOsy('<pre>' + response.msg + '</pre>');
                    //Message.successOsy('<pre>Run finished in ' + response.time + ' \n' + response.msg + '</pre>');
                }
                else{
                    Message.dangerOsy('<pre>' + response.msg + '</pre>');
                }


                $(".batchOutput").show();
                $("#osy-batchOutput").empty();
                $("#osy-batchOutput").html('<pre class="log-output">' + response.log+ '</pre>');

            })
            .catch(error => {
                Message.bigBoxDanger(error)
            })

        });

        $("#osy-cleanUp").off('click');
        $("#osy-cleanUp").on('click', function (event) {
            //console.log('BATCH RUN')
            Pace.restart();
            Message.loaderStart('Recycle all results! Plese wait...');

            Osemosys.cleanUp(model.casename)
            .then(response => {
                Message.loaderEnd();
                $(".runOutput").hide();
                $(".DataFile").hide();
                $(".lpOutput").hide(); $(".highsOutput").hide();
                $(".Results").hide();
                $(".batchOutput").hide();
                $("#osy-runCaseDiv").hide();
                $("#osy-runOutput").empty();
                $("#osy-lpOutput").empty();
                $('.Cases').tab('show');

                console.log('response clean up ', response) 

                Sidebar.Reload(model.casename);
                Message.clearMessages();

                if(response.status_code == 'success'){
                    Message.bigBoxSuccess('Delete message', response.message, 3000);
                    //Message.successOsy('<pre>' + response.message + '</pre>');
                    //Message.successOsy('<pre>Run finished in ' + response.time + ' \n' + response.msg + '</pre>');
                }
                else{
                    Message.dangerOsy('<pre>' + response.message + '</pre>');
                }
            })
            .catch(error => {
                Message.bigBoxDanger(error)
            })

        });

        Message.loaderEnd();
    }
}







// ---------------------------------------------------------------- HiGHS settings
// The panel writes nothing anywhere: it is read only when RUN MODEL is pressed,
// and only while a HiGHS option is selected. Every field may be left empty, in
// which case the solver keeps the default it has always used.
const HIGHS_FIELDS = ['solver', 'presolve', 'parallel', 'threads', 'time_limit',
                     'mip_rel_gap', 'pdlp_optimality_tolerance'];

window.readHighsOptions = function () {
    let opts = {};
    HIGHS_FIELDS.forEach(function (key) {
        let value = $('#hi-' + key).val();
        if (value !== undefined && value !== null && String(value).trim() !== '') {
            opts[key] = String(value).trim();
        }
    });
    return Object.keys(opts).length ? opts : null;
};

window.syncHighsOptionsButton = function () {
    let solver = $('#osy-solverSelect').val() || '';
    let usable = $('#osy-solverSelect').is(':visible') && solver.indexOf('highs') === 0;
    if (usable) {
        $('#osy-highsOptionsBtn').show();
    } else {
        $('#osy-highsOptionsBtn').hide();
        $('#osy-highsOptions').hide();
    }
};

$(document)
    .on('change', '#osy-solverSelect', function () { window.syncHighsOptionsButton(); })
    .on('click', '#osy-highsOptionsBtn', function (e) {
        e.preventDefault();
        $('#osy-highsOptions').toggle();
    })
    .on('click', '#osy-highsOptionsClose', function (e) {
        e.preventDefault();
        $('#osy-highsOptions').hide();
    })
    .on('click', '#osy-highsOptionsReset', function (e) {
        e.preventDefault();
        $('#hi-solver').val('choose');
        $('#hi-presolve').val('choose');
        $('#hi-parallel').val('on');
        $('#hi-threads, #hi-time_limit, #hi-mip_rel_gap, #hi-pdlp_optimality_tolerance').val('');
    })
    .on('click', function (e) {          // click anywhere else closes it
        if (!$(e.target).closest('#osy-highsOptions, #osy-highsOptionsBtn').length) {
            $('#osy-highsOptions').hide();
        }
    });


// -------------------------------------------------------- live run progress
// /run blocks until everything is finished, so the stage is read from /progress
// on a second connection while it works.
let runProgressTimer = null;

function startRunProgress(casename, caserunname) {
    stopRunProgress();
    let tick = function () {
        Osemosys.progress(casename, caserunname).then(function (p) {
            if (!p || p.status !== 'running') { return; }
            let mins = Math.floor(p.stage_elapsed / 60);
            let secs = Math.round(p.stage_elapsed % 60);
            let clock = mins > 0 ? (mins + 'm ' + secs + 's') : (secs + 's');
            $('#loadermain h4').text(
                p.percent + '%  -  step ' + p.stage_index + ' of ' + p.stage_count +
                '  -  ' + p.current + '  ' + clock);
        });
    };
    tick();
    runProgressTimer = setInterval(tick, 700);
}

function stopRunProgress(casename, caserunname) {
    if (runProgressTimer) { clearInterval(runProgressTimer); runProgressTimer = null; }
    if (casename) { showRunSummary(casename, caserunname); }
}

// once the run has finished every stage's real time is known, so the summary
// reports those instead of the estimate shown while it was running
function showRunSummary(casename, caserunname) {
    Osemosys.progress(casename, caserunname).then(function (p) {
        if (!p || !p.done || !p.done.length) { return; }
        let rows = p.done.map(function (d) {
            let share = (d.percent || 0);
            return '<tr>' +
                '<td style="padding:4px 12px 4px 0;">' + d.name + '</td>' +
                '<td style="padding:4px 12px 4px 0; text-align:right;">' + d.seconds.toFixed(2) + ' s</td>' +
                '<td style="padding:4px 12px 4px 0; text-align:right;">' + share.toFixed(1) + '%</td>' +
                '<td style="width:220px;"><div style="background:#e1e0d9; height:10px; border-radius:5px;">' +
                '<div style="background:#2a78d6; height:10px; border-radius:5px; width:' + share + '%;"></div>' +
                '</div></td></tr>';
        }).join('');
        let csvUrl = Base.apiUrl() + 'downloadRunSummary?caserunname=' +
                     encodeURIComponent(caserunname);
        let xlsxUrl = Base.apiUrl() + 'downloadRunSummaryXlsx?caserunname=' +
                      encodeURIComponent(caserunname);
        // the solver's figure, the constant the matrix does not carry, and the sum
        let money = function (v) {
            return Number(v).toLocaleString(undefined, {maximumFractionDigits: 4});
        };
        let hasObjective = !(p.objective === '' || p.objective === null ||
                             typeof p.objective === 'undefined');
        let fixedCost = (p.constant === null || typeof p.constant === 'undefined')
                        ? null : Number(p.constant);
        let totalCost = (hasObjective && fixedCost !== null)
                        ? Number(p.objective) + fixedCost : null;

        $('#osy-runSummary').html(
            '<div style="padding:12px 4px;">' +
            '<a class="btn btn-default btn-sm" style="float:right; border-radius:8px; margin-left:6px;" ' +
            'href="' + xlsxUrl + '" title="The same summary as a formatted workbook, ' +
            'built fresh each time"><i class="fa fa-file-excel-o"></i> .xlsx</a>' +
            '<a class="btn btn-default btn-sm" style="float:right; border-radius:8px;" ' +
            'href="' + csvUrl + '" title="Every run of this case: solver, settings, ' +
            'stage times and peak memory"><i class="fa fa-download"></i> .csv</a>' +
            '<button id="osy-clearRunSummary" class="btn btn-default btn-sm" ' +
            'style="float:right; border-radius:8px; margin-right:6px;" ' +
            'data-caserun="' + caserunname + '" ' +
            'title="Start a fresh record. The runs collected so far are kept as a ' +
            'dated file in the case folder, not deleted."><i class="fa fa-eraser"></i> ' +
            'New record</button>' +
            '<div style="margin-bottom:8px;">Solver: <b>' + (p.solver || '') + '</b>' +
            '  -  total <b>' + (p.total_seconds || 0).toFixed(2) + ' s</b>' +
            (p.peak_mb ? '  -  peak memory <b>' + p.peak_mb + ' MB</b>' : '') + '</div>' +
            (p.outcome ? '<div style="margin-bottom:6px;">Result: <b style="color:' +
                      (p.outcome === 'Optimal' ? '#3c763d' : '#a94442') + ';">' +
                      p.outcome + '</b>' +
                      (!hasObjective ? '' : '  -  objective <b>' +
                       money(totalCost !== null ? totalCost : p.objective) + '</b>') +
                      '</div>' : '') +
            (hasObjective && fixedCost ?
                      '<div style="margin-bottom:6px; font-size:12px; color:#5f5e5a;">' +
                      'includes <b>' + money(fixedCost) + '</b> fixed cost of existing ' +
                      'capacity, which the matrix does not carry  -  the solver ' +
                      'returned ' + money(p.objective) + '</div>' : '') +
            (hasObjective && fixedCost === null && (p.solver || '').indexOf('mosox') >= 0 ?
                      '<div style="margin-bottom:6px; font-size:12px; color:#8a6d3b;">' +
                      'fixed cost not recovered on the mosox path, so this total may ' +
                      'be short</div>' : '') +
            (p.rows ? '<div style="margin-bottom:10px; color:#5f5e5a;">' +
                      (p.kind ? '<b>' + p.kind + '</b>  -  ' : '') +
                      Number(p.rows).toLocaleString() + ' rows  -  ' +
                      Number(p.cols).toLocaleString() + ' columns  -  ' +
                      Number(p.nonzeros).toLocaleString() + ' non-zeros' +
                      (p.integers ? '  -  <b>' + Number(p.integers).toLocaleString() +
                       '</b> integer columns' : '') + '</div>' : '') +
            '<table style="font-size:13px;">' + rows + '</table></div>');
        $('.runSummary').show();
    });
}


// "New record" archives the existing file rather than deleting it
$(document).on('click', '#osy-clearRunSummary', function (e) {
    e.preventDefault();
    let caserun = $(this).data('caserun');
    if (!confirm('Start a fresh run record?\n\nThe runs collected so far are kept ' +
                 'as a dated file in the case folder.')) { return; }
    Osemosys.clearRunSummary(caserun).then(function (r) {
        $('#osy-runSummary').html(
            '<div style="padding:12px 4px; color:#5f5e5a;">' +
            (r && r.message ? r.message : 'Record cleared.') +
            '<br>The next run starts a new record.</div>');
    });
});
